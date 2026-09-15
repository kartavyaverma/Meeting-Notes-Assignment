"""Command line: turn transcript files or folders into Notion pages, or set up the database.

    python .claude/skills/meeting-notes/meeting_notes.py transcripts/ [--dry-run] [--force]
    python .claude/skills/meeting-notes/meeting_notes.py --init-db

Exit codes: 0 = every file created, skipped or previewed; 1 = at least one file failed;
2 = setup problem (missing keys, bad paths, unreachable or incomplete Notion database).
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional, Sequence, Tuple

from . import __version__
from .api import ApiError
from .config import ConfigError, Settings, load_dotenv
from .gemini import GeminiClient, cost_usd
from .notion import NotionClient
from .transcript import content_hash, precheck, read_transcript
from .verification import fix_date, verify_action_items

EXIT_OK, EXIT_FAILED, EXIT_CONFIG = 0, 1, 2
STOP_BATCH_STATUSES = (429, 503)   # Gemini overloaded or out of quota: the rest of the batch would fail too

Output = Callable[[str], None]


@dataclass
class Result:
    name: str
    status: str   # created | skipped | dry run | failed | not run
    detail: str


def collect_files(paths: Sequence[str]) -> List[Path]:
    """Expand folders to their .txt files (sorted), keep explicit files, drop duplicates."""
    files: List[Path] = []
    for path in map(Path, paths):
        if path.is_dir():
            files += sorted(f for f in path.glob("*.txt") if f.name.lower() != "readme.txt")
        elif path.is_file():
            files.append(path)
        else:
            raise ConfigError(f"Not found: {path}")
    unique, seen = [], set()
    for f in files:
        key = f.resolve()
        if key not in seen:
            seen.add(key)
            unique.append(f)
    if not unique:
        raise ConfigError("No .txt transcripts found.")
    return unique


class Runner:
    """Processes a batch of transcripts. One bad file never stops the others, except when Gemini itself
    is overloaded or out of quota, where continuing would only burn requests."""

    def __init__(self, gemini: GeminiClient, notion: Optional[NotionClient], *,
                 dry_run: bool = False, force: bool = False, out: Output = print) -> None:
        self.gemini = gemini
        self.notion = notion
        self.dry_run = dry_run
        self.force = force
        self.out = out
        self._title_column = ""

    def run(self, files: Sequence[Path]) -> List[Result]:
        if self.notion is not None and not self.dry_run:
            self._title_column = self.notion.check_database()
        results: List[Result] = []
        for index, path in enumerate(files):
            self.out(f"\n== {path.name}")
            stop = False
            try:
                status, detail = self._process(path)
            except ApiError as e:
                status, detail = "failed", str(e)
                stop = e.service == "Gemini" and e.status in STOP_BATCH_STATUSES
            except OSError as e:
                status, detail = "failed", f"can't read file ({e.strerror or e})"
            self.out(f"  -> {status}: {detail}")
            results.append(Result(path.name, status, detail))
            if stop:
                results += [Result(rest.name, "not run",
                                   "Gemini overloaded or out of quota; re-run later (imported transcripts are skipped)")
                            for rest in files[index + 1:]]
                break
        return results

    def _process(self, path: Path) -> Tuple[str, str]:
        text = read_transcript(path)
        problem = precheck(text)
        if problem:
            return "skipped", problem
        digest = content_hash(text)
        if not self.dry_run and not self.force:
            existing = self.notion.find_existing(path.name, digest)
            if existing:
                return "skipped", f"already in Notion: {existing} (use --force to add it again)"

        notes, usage = self.gemini.extract(text, path.name)
        if not notes["is_meeting_transcript"]:
            reason = notes["rejection_reason"] or "no reason given"
            return "skipped", f"Gemini says this isn't a usable meeting transcript: {reason}"
        fix_date(notes)
        verify_action_items(notes, text)
        self._show(notes, usage)

        if self.dry_run:
            return "dry run", "nothing written to Notion"
        url = self.notion.create_page(notes, path.name, digest, usage, self._title_column, self.gemini.model)
        return "created", url

    def _show(self, notes: dict, usage: dict) -> None:
        out = self.out
        out(f"  Title:     {notes['title']}")
        out(f"  Date:      {notes['date'] or '(not stated)'}")
        out(f"  Attendees: {', '.join(a['name'] for a in notes['attendees']) or '(none identified)'}")
        out(f"  Decisions: {len(notes['decisions'])}")
        for decision in notes["decisions"]:
            out(f"    - {decision}")
        out(f"  Action items: {len(notes['action_items'])}")
        for item in notes["action_items"]:
            mark = "⚠️ " if item["verify"] else "✅"
            out(f"    {mark} {item['task']}  [owner: {item['owner'] or 'Unassigned'}; due: {item['due'] or '-'}]")
            for reason in item["verify"]:
                out(f"         please verify: {reason}")
        for assumption in notes["assumptions"]:
            out(f"  Assumption: {assumption}")
        cost = cost_usd(usage, self.gemini.settings)
        out(f"  Gemini usage: {usage.get('promptTokenCount', 0)} in, {usage.get('candidatesTokenCount', 0)} out, "
            f"{usage.get('thoughtsTokenCount', 0)} thinking" + (f", ~${cost:.4f}" if cost is not None else ""))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="meeting-notes",
        description="Turn call transcripts into structured Notion meeting notes using Gemini 3.8 Flash.",
    )
    parser.add_argument("paths", nargs="*", help="transcript .txt files, or folders containing them")
    parser.add_argument("--dry-run", action="store_true", help="extract and print the notes without writing to Notion")
    parser.add_argument("--force", action="store_true", help="import even if the transcript is already in Notion")
    parser.add_argument("--init-db", action="store_true", help="add any missing columns to the Notion database, then exit")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    _utf8_console()
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.init_db and (args.paths or args.dry_run or args.force):
        parser.error("--init-db doesn't take transcripts or other options")
    if not args.init_db and not args.paths:
        parser.error("give at least one transcript file or folder (or --init-db)")

    out: Output = lambda line: print(line, flush=True)
    load_dotenv()
    try:
        if args.init_db:
            return _init_db(out)
        files = collect_files(args.paths)
        settings = Settings.from_env(need_gemini=True, need_notion=not args.dry_run)
        notion = None if args.dry_run else NotionClient(settings)
        runner = Runner(GeminiClient(settings, notify=out), notion, dry_run=args.dry_run, force=args.force, out=out)
        results = runner.run(files)
    except (ConfigError, ApiError) as e:
        print(f"error: {e}", file=sys.stderr)
        return EXIT_CONFIG

    out(f"\nDone: {len(results)} file(s)")
    width = max(len(r.status) for r in results)
    for r in results:
        out(f"  {r.status:<{width}}  {r.name}  {r.detail}")
    return EXIT_FAILED if any(r.status == "failed" for r in results) else EXIT_OK


def _init_db(out: Output) -> int:
    added = NotionClient(Settings.from_env(need_gemini=False, need_notion=True)).init_database()
    out(f"Added columns: {', '.join(added)}" if added else "The database already has every column the skill needs.")
    return EXIT_OK


def _utf8_console() -> None:
    """Windows consoles default to a legacy code page that can't print ✅/⚠️."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")
