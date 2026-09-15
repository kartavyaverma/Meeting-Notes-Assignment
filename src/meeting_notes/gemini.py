"""Extraction with Gemini 3.8 Flash: prompt, response schema, retries, response parsing and cost."""

from __future__ import annotations

import json
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from .api import ApiError, request_json
from .config import Settings

API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
RETRY_WAITS_S = (20, 40)   # few, spaced retries: failed calls can still count against quota
RETRY_STATUSES = (429, 500, 503)
OWNER_STATUSES = ("explicit", "implied", "unassigned")

Notes = Dict[str, Any]
Usage = Dict[str, int]

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
  - evidence: the exact words from ONE speaker's line where the commitment was made, copied verbatim
    (at least 5 words). Do not paraphrase, do not join several lines, do not include speaker names
    or timestamps.
  - due: the deadline as said ("by Friday", "this week"), else empty.
  - soft_commitment: true for hedged promises ("I'll try", "no promises", "probably").
- assumptions: each interpretation you had to make, one sentence each. Empty if none."""

_STR = {"type": "STRING"}
SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "is_meeting_transcript": {"type": "BOOLEAN"},
        "rejection_reason": _STR,
        "title": _STR,
        "date": _STR,
        "attendees": {"type": "ARRAY", "items": {"type": "OBJECT",
                      "properties": {"name": _STR, "role": _STR}, "required": ["name", "role"]}},
        "summary": _STR,
        "decisions": {"type": "ARRAY", "items": _STR},
        "action_items": {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {
            "task": _STR,
            "owner": _STR,
            "owner_status": {"type": "STRING", "enum": list(OWNER_STATUSES)},
            "evidence": _STR,
            "due": _STR,
            "soft_commitment": {"type": "BOOLEAN"},
        }, "required": ["task", "owner", "owner_status", "evidence", "due", "soft_commitment"]}},
        "assumptions": {"type": "ARRAY", "items": _STR},
    },
    "required": ["is_meeting_transcript", "rejection_reason", "title", "date", "attendees",
                 "summary", "decisions", "action_items", "assumptions"],
}


class GeminiClient:
    """Calls Gemini's generateContent endpoint. `http`, `sleep` and `notify` are injectable for tests."""

    def __init__(
        self,
        settings: Settings,
        http: Callable[..., Dict[str, Any]] = request_json,
        sleep: Callable[[float], None] = time.sleep,
        notify: Callable[[str], None] = print,
    ) -> None:
        self.settings = settings
        self._http = http
        self._sleep = sleep
        self._notify = notify

    @property
    def model(self) -> str:
        return self.settings.gemini_model

    def extract(self, text: str, source: str) -> Tuple[Notes, Usage]:
        """Extract structured notes from one transcript. Raises ApiError (service "Gemini") on failure."""
        body = {
            "systemInstruction": {"parts": [{"text": PROMPT}]},
            "contents": [{"role": "user", "parts": [{"text": f"Transcript file: {source}\n\n{text}"}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": SCHEMA,
                "thinkingConfig": {"thinkingLevel": "low"},
            },
        }
        response = self._post(body)
        return parse_response(response), response.get("usageMetadata", {})

    def _post(self, body: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{API_BASE}/{self.model}:generateContent"
        headers = {"x-goog-api-key": self.settings.gemini_api_key}
        retries = 0
        while True:
            try:
                return self._http("POST", url, headers, body)
            except ApiError as e:
                message = e.message.lower()
                config = body["generationConfig"]
                if e.status == 400 and "thinking" in message and "thinkingConfig" in config:
                    del config["thinkingConfig"]   # model doesn't accept this setting; retry without it
                    continue
                if e.status == 404:
                    raise ApiError(404, f"model {self.model!r} isn't available to this API key; check GEMINI_MODEL",
                                   "Gemini") from None
                if e.status == 429 and "quota" in message:
                    raise ApiError(429, f"quota used up; try again later or enable billing ({e.message})",
                                   "Gemini") from None
                if e.status in RETRY_STATUSES and retries < len(RETRY_WAITS_S):
                    wait = RETRY_WAITS_S[retries]
                    retries += 1
                    self._notify(f"  Gemini busy ({e.status}), retrying in {wait}s ({retries}/{len(RETRY_WAITS_S)})")
                    self._sleep(wait)
                    continue
                raise ApiError(e.status, e.message, "Gemini") from None


def parse_response(response: Dict[str, Any]) -> Notes:
    """Turn a generateContent response into normalized notes, or raise ApiError if it's unusable."""
    candidates = response.get("candidates") or []
    if not candidates:
        reason = (response.get("promptFeedback") or {}).get("blockReason", "no reason given")
        raise ApiError(0, f"returned no answer ({reason})", "Gemini")
    candidate = candidates[0]
    if candidate.get("finishReason") != "STOP":
        raise ApiError(0, f"stopped before finishing ({candidate.get('finishReason')})", "Gemini")
    parts = (candidate.get("content") or {}).get("parts") or []
    raw = "".join(part.get("text", "") for part in parts if not part.get("thought"))
    try:
        data = json.loads(raw)
    except ValueError:
        raise ApiError(0, "returned invalid JSON", "Gemini") from None
    if not isinstance(data, dict):
        raise ApiError(0, "returned JSON that isn't an object", "Gemini")
    return normalize_notes(data)


def normalize_notes(data: Dict[str, Any]) -> Notes:
    """Coerce model output into the exact shape the rest of the pipeline expects.

    Every list is freshly created, malformed entries are dropped, and an unknown owner_status becomes
    "unassigned" so it gets flagged rather than trusted.
    """
    attendees = [
        {"name": _text(a.get("name")), "role": _text(a.get("role"))}
        for a in _list(data.get("attendees")) if isinstance(a, dict) and _text(a.get("name"))
    ]
    items = []
    for raw in _list(data.get("action_items")):
        if not isinstance(raw, dict) or not _text(raw.get("task")):
            continue
        status = raw.get("owner_status")
        items.append({
            "task": _text(raw.get("task")),
            "owner": _text(raw.get("owner")),
            "owner_status": status if status in OWNER_STATUSES else "unassigned",
            "evidence": _text(raw.get("evidence")),
            "due": _text(raw.get("due")),
            "soft_commitment": raw.get("soft_commitment") is True,
        })
    return {
        "is_meeting_transcript": data.get("is_meeting_transcript") is True,
        "rejection_reason": _text(data.get("rejection_reason")),
        "title": _text(data.get("title")) or "Untitled meeting",
        "date": _text(data.get("date")),
        "attendees": attendees,
        "summary": _text(data.get("summary")),
        "decisions": _strings(data.get("decisions")),
        "action_items": items,
        "assumptions": _strings(data.get("assumptions")),
    }


def cost_usd(usage: Usage, settings: Settings) -> Optional[float]:
    """Cost of one call, or None if prices aren't configured. Thinking tokens bill at the output price."""
    if settings.input_usd_per_m is None or settings.output_usd_per_m is None:
        return None
    output_tokens = usage.get("candidatesTokenCount", 0) + usage.get("thoughtsTokenCount", 0)
    return (usage.get("promptTokenCount", 0) * settings.input_usd_per_m
            + output_tokens * settings.output_usd_per_m) / 1_000_000


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _strings(value: Any) -> List[str]:
    return [s.strip() for s in _list(value) if isinstance(s, str) and s.strip()]
