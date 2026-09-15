"""Reading transcripts, rejecting unusable ones before any API call, and splitting them by speaker."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from pathlib import Path
from typing import List, Optional

MIN_WORDS = 40            # below this it can't be a meeting worth notes
MIN_LETTER_RATIO = 0.6    # below this the file is mostly symbols or numbers

# "[00:01:02] Priya Nair: text" (Zoom, Teams) and "Priya Nair  0:12" on its own line (Otter)
SPEAKER_INLINE = re.compile(r"^\s*(?:\[[\d:.]+\]\s*)?([A-Z][\w.'-]*(?: [A-Z][\w.'-]*){0,3})\s*:\s*(.*)$")
SPEAKER_HEADER = re.compile(r"^\s*([A-Z][\w.'-]*(?: [A-Z][\w.'-]*){0,3})\s+\d{1,2}:\d{2}(?::\d{2})?\s*$")


def read_transcript(path: Path) -> str:
    """Read a transcript whatever its encoding: UTF-16 exports, UTF-8 with or without BOM, or Windows-1252."""
    raw = path.read_bytes()
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return raw.decode("utf-16")
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("cp1252", errors="replace")


def precheck(text: str) -> Optional[str]:
    """Return why a transcript is unusable, or None. Runs locally so bad files never cost an API call."""
    if not text.strip():
        return "file is empty"
    visible = [ch for ch in text if not ch.isspace()]
    if sum(_is_letter(ch) for ch in visible) / len(visible) < MIN_LETTER_RATIO:
        return "mostly non-letter characters, looks garbled"
    words = [w for w in re.findall(r"\w+", text) if any(ch.isalpha() for ch in w)]
    if len(words) < MIN_WORDS:
        return f"only {len(words)} words, too short to be a meeting transcript"
    return None


def _is_letter(ch: str) -> bool:
    # Combining marks count as letters, so scripts like Devanagari aren't mistaken for garbage.
    return ch.isalpha() or unicodedata.category(ch).startswith("M")


def content_hash(text: str) -> str:
    """Fingerprint of a transcript's content, ignoring line endings and trailing spaces.

    Used for duplicate detection: a re-saved or renamed copy is recognised, and two different
    transcripts that happen to share a filename are not confused.
    """
    lines = text.replace("\r\n", "\n").replace("\r", "\n").strip().split("\n")
    canonical = "\n".join(line.rstrip() for line in lines)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def normalize(text: str) -> str:
    """Lowercase, punctuation to spaces, whitespace collapsed: the form quotes are compared in."""
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", text.lower())).strip()


def utterances(text: str) -> List[str]:
    """Each line of speech prefixed with its speaker, normalized."""
    out: List[str] = []
    speaker = ""
    for line in text.splitlines():
        if not line.strip():
            continue
        header = SPEAKER_HEADER.match(line)
        if header:
            speaker = header.group(1)
            continue
        inline = SPEAKER_INLINE.match(line)
        if inline:
            speaker, line = inline.group(1), inline.group(2)
        out.append(normalize(f"{speaker} {line}"))
    return out
