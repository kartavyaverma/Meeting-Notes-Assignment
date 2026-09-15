#!/usr/bin/env python3
"""Turn call transcripts into structured Notion meeting-notes pages.

Gemini 3.8 Flash extracts the notes; Notion's REST API stores them.
Standard library only.

Usage:
  python meeting_notes.py <transcript.txt | folder> [...] [--dry-run] [--force]
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import date, datetime
from pathlib import Path

MODEL = "gemini-3.8-flash"
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"
NOTION_URL = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"
MIN_WORDS = 40          # below this it can't be a meeting worth notes
TEXT_LIMIT = 2000       # Notion's max characters per rich-text item
LIST_LIMIT = 30         # keep pages under Notion's 100-blocks-per-request limit
RETRY_WAITS = [20, 40]  # seconds; few, spaced retries, since failed calls can still count against quota
REQUIRED_COLUMNS = {"Date": "date", "Attendees": "rich_text", "Needs review": "checkbox", "Source": "rich_text"}

PROMPT = """You turn a raw call transcript into structured meeting notes for a busy team.

Rules:
- Use only what is in the transcript. Never invent attendees, decisions, dates or tasks.
- If the text is not a conversation between people (empty, garbled, random text, no meeting content),
  set is_meeting_transcript to false, explain why in rejection_reason, and leave the other fields empty.
- title: short and specific, e.g. "BrightPath Dental: website rebuild kickoff".
- date: YYYY-MM-DD only if the transcript states the date. Otherwise empty. Do not guess.
- attendees: people who spoke or were introduced as present. role only if stated, else empty.
- summary: 2-4 plain sentences on what the meeting was about and where it landed.
- decisions: only things the group actually agreed. Topics deferred or left open are not decisions.
- action_items: every task someone agreed to do or was clearly asked to do.
  - owner: the person who ends up responsible. Follow hand-offs: if A asks B, B says C has it, and C
    agrees, the owner is C.
  - owner_status: "explicit" only when a named person clearly commits ("I'll send it Friday") or is
    asked by name and accepts. "implied" when you are inferring the person (e.g. "we'll send the quote",
    or "Will do" without restating the task). "unassigned" when nobody took it ("someone should...",
    "we need to...") - then owner is empty.
  - evidence: the exact words from the transcript where the commitment was made, copied verbatim
    (at least 5 words). Do not paraphrase.
  - due: the deadline as said ("by Friday", "this week"), else empty.
  - soft_commitment: true for hedged promises ("I'll try", "no promises", "probably").
- assumptions: each interpretation you had to make, one sentence each. Empty if none."""

STR = {"type": "STRING"}
SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "is_meeting_transcript": {"type": "BOOLEAN"},
        "rejection_reason": STR,
        "title": STR,
        "date": STR,
        "attendees": {"type": "ARRAY", "items": {"type": "OBJECT",
                      "properties": {"name": STR, "role": STR}, "required": ["name", "role"]}},
        "summary": STR,
        "decisions": {"type": "ARRAY", "items": STR},
        "action_items": {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {
            "task": STR, "owner": STR,
            "owner_status": {"type": "STRING", "enum": ["explicit", "implied", "unassigned"]},
            "evidence": STR, "due": STR, "soft_commitment": {"type": "BOOLEAN"},
        }, "required": ["task", "owner", "owner_status", "evidence", "due", "soft_commitment"]}},
        "assumptions": {"type": "ARRAY", "items": STR},
    },
    "required": ["is_meeting_transcript", "rejection_reason", "title", "date", "attendees",
                 "summary", "decisions", "action_items", "assumptions"],
}


class ApiError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


def http(method, url, headers, body=None):
    req = urllib.request.Request(url, method=method, headers={**headers, "Content-Type": "application/json"},
                                 data=None if body is None else json.dumps(body).encode())
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        try:
            err = json.load(e)
        except ValueError:
            err = {}
        inner = err.get("error")
        msg = err.get("message") or (inner.get("message") if isinstance(inner, dict) else None) or e.reason
        raise ApiError(e.code, msg) from None
    except urllib.error.URLError as e:
        raise ApiError(0, f"network error: {e.reason}") from None


# ---------- setup ----------

def load_env():
    """Read the nearest .env without overriding variables already set in the shell."""
    here = Path.cwd()
    for d in [here, *here.parents, *Path(__file__).resolve().parents]:
        f = d / ".env"
        if f.is_file():
            for line in f.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip("\"'"))
            return


def require_env(dry_run):
    need = ["GEMINI_API_KEY"] + ([] if dry_run else ["NOTION_TOKEN", "NOTION_DATABASE_ID"])
    missing = [k for k in need if not os.environ.get(k) or os.environ[k].startswith("your-")]
    if missing:
        sys.exit(f"Missing in .env: {', '.join(missing)}. Copy .env.example to .env and fill them in.")


def collect_files(args):
    files = []
    for p in map(Path, args):
        if p.is_dir():
            files += sorted(f for f in p.glob("*.txt") if f.name.lower() != "readme.txt")
        elif p.is_file():
            files.append(p)
        else:
            sys.exit(f"Not found: {p}")
    if not files:
        sys.exit("No .txt transcripts found.")
    return files


# ---------- transcript ----------

def read_transcript(path):
    raw = path.read_bytes()
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return raw.decode("utf-16")
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("cp1252", errors="replace")


def precheck(text):
    """Cheap local checks so obviously bad input never costs an API call."""
    if not text.strip():
        return "file is empty"
    visible = sum(not c.isspace() for c in text)
    if sum(c.isalpha() for c in text) / visible < 0.6:
        return "mostly non-letter characters, looks garbled"
    words = [w for w in re.findall(r"\w+", text) if any(c.isalpha() for c in w)]
    if len(words) < MIN_WORDS:
        return f"only {len(words)} words, too short to be a meeting transcript"
    return None


def norm(s):
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", s.lower())).strip()


SPEAKER_INLINE = re.compile(r"^\s*(?:\[[\d:.]+\]\s*)?([A-Z][\w.'-]*(?: [A-Z][\w.'-]*){0,3})\s*:\s*(.*)$")
SPEAKER_HEADER = re.compile(r"^\s*([A-Z][\w.'-]*(?: [A-Z][\w.'-]*){0,3})\s+\d{1,2}:\d{2}(?::\d{2})?\s*$")


def utterances(text):
    """Pair each line of speech with its speaker. Handles 'Name: text' (Zoom/Teams) and
    'Name  0:12' header lines followed by text (Otter)."""
    out, speaker = [], ""
    for line in text.splitlines():
        if not line.strip():
            continue
        if m := SPEAKER_HEADER.match(line):
            speaker = m.group(1)
            continue
        if m := SPEAKER_INLINE.match(line):
            speaker, line = m.group(1), m.group(2)
        out.append(norm(f"{speaker} {line}"))
    return out


def check_owners(notes, text):
    """Don't trust the model's own confidence: every owner must be backed by a verbatim quote
    that comes from, or names, that person. Anything else is marked 'please verify'."""
    whole, said = norm(text), utterances(text)
    for item in notes["action_items"]:
        owner, quote, reasons = item["owner"].strip(), norm(item["evidence"]), []
        if not owner or item["owner_status"] == "unassigned":
            reasons.append("no owner named in the transcript")
        elif item["owner_status"] == "implied":
            reasons.append(f"owner inferred, not stated (best guess: {owner})")
        if not quote or quote not in whole:
            reasons.append("supporting quote not found in the transcript")
        elif owner:
            first = re.escape(norm(owner).split()[0])
            lines = [u for u in said if quote in u]
            if lines and not any(re.search(rf"\b{first}\b", u) for u in lines):
                reasons.append(f"the quote isn't from or addressed to {owner}")
        if item["soft_commitment"]:
            reasons.append("soft commitment, may not happen")
        item["verify"] = reasons


# ---------- Gemini ----------

def extract(text, source):
    body = {
        "systemInstruction": {"parts": [{"text": PROMPT}]},
        "contents": [{"role": "user", "parts": [{"text": f"Transcript file: {source}\n\n{text}"}]}],
        "generationConfig": {"responseMimeType": "application/json", "responseSchema": SCHEMA,
                             "thinkingConfig": {"thinkingLevel": "low"}},
    }
    headers = {"x-goog-api-key": os.environ["GEMINI_API_KEY"]}
    for attempt in range(len(RETRY_WAITS) + 1):
        try:
            r = http("POST", GEMINI_URL, headers, body)
            break
        except ApiError as e:
            if e.status == 400 and "thinking" in str(e).lower() and "thinkingConfig" in body["generationConfig"]:
                del body["generationConfig"]["thinkingConfig"]   # model doesn't accept this setting
                continue
            if e.status == 429 and "quota" in str(e).lower():
                raise ApiError(429, f"Gemini quota used up, try again later or enable billing: {e}") from None
            if e.status in (429, 500, 503) and attempt < len(RETRY_WAITS):
                wait = RETRY_WAITS[attempt]
                print(f"  Gemini busy ({e.status}), retrying in {wait}s ({attempt + 1}/{len(RETRY_WAITS)})", flush=True)
                time.sleep(wait)
                continue
            raise ApiError(e.status, f"Gemini: {e}") from None
    cand = (r.get("candidates") or [{}])[0]
    if cand.get("finishReason") != "STOP":
        raise ApiError(0, f"Gemini stopped early ({cand.get('finishReason') or r.get('promptFeedback')})")
    raw = "".join(p.get("text", "") for p in cand["content"]["parts"] if not p.get("thought"))
    try:
        data = json.loads(raw)
    except ValueError:
        raise ApiError(0, "Gemini returned invalid JSON") from None
    defaults = {"is_meeting_transcript": False, "rejection_reason": "", "title": "Untitled meeting", "date": "",
                "attendees": [], "summary": "", "decisions": [], "action_items": [], "assumptions": []}
    return {k: data.get(k, v) for k, v in defaults.items()}, r.get("usageMetadata", {})


def cost_usd(usage):
    try:
        pin = float(os.environ["GEMINI_INPUT_USD_PER_M"])
        pout = float(os.environ["GEMINI_OUTPUT_USD_PER_M"])
    except (KeyError, ValueError):
        return None
    out = usage.get("candidatesTokenCount", 0) + usage.get("thoughtsTokenCount", 0)  # thinking bills as output
    return (usage.get("promptTokenCount", 0) * pin + out * pout) / 1e6


# ---------- Notion ----------

def notion(method, path, body=None):
    headers = {"Authorization": f"Bearer {os.environ['NOTION_TOKEN']}", "Notion-Version": NOTION_VERSION}
    try:
        return http(method, NOTION_URL + path, headers, body)
    except ApiError as e:
        if e.status == 401:
            raise ApiError(401, "Notion rejected NOTION_TOKEN. Copy the access token again from "
                                "Developer tools -> Connections.") from None
        if e.status == 404:
            raise ApiError(404, "Notion can't see the database. Check NOTION_DATABASE_ID, and that the database "
                                "has the connection added (the ... menu -> Connections).") from None
        raise ApiError(e.status, f"Notion: {e}") from None


def check_database():
    """One call up front, so a broken connection fails before any Gemini tokens are spent."""
    db = notion("GET", f"/databases/{os.environ['NOTION_DATABASE_ID']}")
    props = {name: p["type"] for name, p in db["properties"].items()}
    wrong = [f"{n} ({t})" for n, t in REQUIRED_COLUMNS.items() if props.get(n) != t]
    if wrong:
        sys.exit(f"Notion database is missing columns: {', '.join(wrong)}")
    return next(name for name, t in props.items() if t == "title")


def already_imported(source):
    r = notion("POST", f"/databases/{os.environ['NOTION_DATABASE_ID']}/query",
               {"filter": {"property": "Source", "rich_text": {"equals": source}}, "page_size": 1})
    return r["results"][0]["url"] if r["results"] else None


def rt(text):
    text = str(text or "")
    return [{"type": "text", "text": {"content": text[i:i + TEXT_LIMIT]}} for i in range(0, len(text), TEXT_LIMIT)]


def block(kind, text, **extra):
    return {"object": "block", "type": kind, kind: {"rich_text": rt(text), **extra}}


def bullets(items, empty):
    if not items:
        return [block("paragraph", empty)]
    out = [block("bulleted_list_item", i) for i in items[:LIST_LIMIT]]
    if len(items) > LIST_LIMIT:
        out.append(block("paragraph", f"...and {len(items) - LIST_LIMIT} more (see transcript)."))
    return out


def page_blocks(notes, source, usage):
    items = notes["action_items"]
    flagged = [i for i in items if i["verify"]]
    blocks = []
    if flagged:
        blocks.append(block("callout", f"{len(flagged)} of {len(items)} action items need a human check before "
                                       "anyone acts on them. See the Status column.",
                            icon={"type": "emoji", "emoji": "⚠️"}, color="yellow_background"))
    elif items:
        blocks.append(block("callout", "Every action item has an owner named in the transcript.",
                            icon={"type": "emoji", "emoji": "✅"}, color="green_background"))

    blocks += [block("heading_2", "Summary"), block("paragraph", notes["summary"] or "No summary.")]
    blocks.append(block("heading_2", "Attendees"))
    blocks += bullets([a["name"] + (f" ({a['role']})" if a.get("role") else "") for a in notes["attendees"]],
                      "No attendees identified.")
    blocks.append(block("heading_2", "Decisions"))
    blocks += bullets(notes["decisions"], "No decisions recorded.")

    blocks.append(block("heading_2", "Action items"))
    if items:
        rows = [["Task", "Owner", "Due", "Status", "From the transcript"]]
        for i in items[:LIST_LIMIT]:
            status = ("⚠️ Please verify: " + "; ".join(i["verify"])) if i["verify"] else "✅ Owner named"
            rows.append([i["task"], i["owner"] or "Unassigned", i["due"] or "—", status, f"“{i['evidence']}”"])
        blocks.append({"object": "block", "type": "table", "table": {
            "table_width": 5, "has_column_header": True,
            "children": [{"object": "block", "type": "table_row", "table_row": {"cells": [rt(c) for c in r]}}
                         for r in rows]}})
    else:
        blocks.append(block("paragraph", "No action items."))

    if notes["assumptions"]:
        blocks.append(block("heading_2", "Assumptions made"))
        blocks += bullets(notes["assumptions"], "")

    tokens = (f"{usage.get('promptTokenCount', 0)} in / {usage.get('candidatesTokenCount', 0)} out / "
              f"{usage.get('thoughtsTokenCount', 0)} thinking tokens")
    blocks += [{"object": "block", "type": "divider", "divider": {}},
               block("paragraph", f"Generated from {source} by {MODEL} on {date.today()} ({tokens}). "
                                  "Check against the transcript before relying on it.")]
    return blocks


def create_page(notes, source, usage, title_prop):
    props = {
        title_prop: {"title": rt(notes["title"])},
        "Attendees": {"rich_text": rt(", ".join(a["name"] for a in notes["attendees"]))},
        "Needs review": {"checkbox": any(i["verify"] for i in notes["action_items"])},
        "Source": {"rich_text": rt(source)},
    }
    if notes["date"]:
        props["Date"] = {"date": {"start": notes["date"]}}
    page = notion("POST", "/pages", {"parent": {"database_id": os.environ["NOTION_DATABASE_ID"]},
                                     "properties": props, "children": page_blocks(notes, source, usage)})
    return page["url"]


# ---------- run ----------

def fix_date(notes):
    try:
        datetime.strptime(notes["date"], "%Y-%m-%d")
    except ValueError:
        if notes["date"]:
            notes["assumptions"].append(f"Date \"{notes['date']}\" wasn't a clear calendar date, so it was left blank.")
        else:
            notes["assumptions"].append("No meeting date was stated in the transcript, so Date was left blank.")
        notes["date"] = ""


def show(notes, usage):
    print(f"  Title:     {notes['title']}")
    print(f"  Date:      {notes['date'] or '(not stated)'}")
    print(f"  Attendees: {', '.join(a['name'] for a in notes['attendees'])}")
    print(f"  Decisions: {len(notes['decisions'])}")
    for d in notes["decisions"]:
        print(f"    - {d}")
    print(f"  Action items: {len(notes['action_items'])}")
    for i in notes["action_items"]:
        mark = "⚠️ " if i["verify"] else "✅"
        print(f"    {mark} {i['task']}  [owner: {i['owner'] or 'Unassigned'}; due: {i['due'] or '-'}]")
        for reason in i["verify"]:
            print(f"         please verify: {reason}")
    for a in notes["assumptions"]:
        print(f"  Assumption: {a}")
    cost = cost_usd(usage)
    print(f"  Gemini usage: {usage.get('promptTokenCount', 0)} in, {usage.get('candidatesTokenCount', 0)} out, "
          f"{usage.get('thoughtsTokenCount', 0)} thinking" + (f", ~${cost:.4f}" if cost is not None else ""))


def process(path, args, title_prop):
    text = read_transcript(path)
    if problem := precheck(text):
        return "skipped", problem
    if not args.dry_run and not args.force and (url := already_imported(path.name)):
        return "skipped", f"already in Notion: {url} (use --force to add it again)"
    notes, usage = extract(text, path.name)
    if not notes["is_meeting_transcript"]:
        return "skipped", f"Gemini says this isn't a usable meeting transcript: {notes['rejection_reason']}"
    fix_date(notes)
    check_owners(notes, text)
    show(notes, usage)
    if args.dry_run:
        return "dry run", "nothing written to Notion"
    return "created", create_page(notes, path.name, usage, title_prop)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="Turn call transcripts into Notion meeting notes.")
    ap.add_argument("paths", nargs="+", help="transcript .txt files or folders of them")
    ap.add_argument("--dry-run", action="store_true", help="extract and print, but don't write to Notion")
    ap.add_argument("--force", action="store_true", help="create a page even if this file was imported before")
    args = ap.parse_args()

    files = collect_files(args.paths)
    load_env()
    require_env(args.dry_run)
    try:
        title_prop = None if args.dry_run else check_database()
    except ApiError as e:
        sys.exit(str(e))

    results = []
    for n, f in enumerate(files):
        print(f"\n== {f.name}", flush=True)
        stop = False
        try:
            status, detail = process(f, args, title_prop)
        except ApiError as e:
            status, detail = "failed", str(e)
            stop = str(e).startswith("Gemini") and e.status in (429, 503)
        except OSError as e:
            status, detail = "failed", f"can't read file ({e.strerror})"
        print(f"  -> {status}: {detail}")
        results.append((f.name, status, detail))
        if stop:   # don't burn quota on the rest of the batch while Gemini is overloaded
            results += [(r.name, "not run", "Gemini overloaded or out of quota; re-run later (created pages are skipped)")
                        for r in files[n + 1:]]
            break

    print(f"\nDone: {len(results)} file(s)")
    for name, status, detail in results:
        print(f"  {status:8} {name}  {detail}")
    sys.exit(1 if any(s == "failed" for _, s, _ in results) else 0)


if __name__ == "__main__":
    main()
