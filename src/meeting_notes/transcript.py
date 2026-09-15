from __future__ import annotations

import hashlib
import re
import unicodedata
from pathlib import Path
from typing import List, Optional

MIN_WORDS = 40
MIN_LETTER_RATIO = 0.6

SPEAKER_INLINE = re.compile(r"^\s*(?:\[[\d:.]+\]\s*)?([A-Z][\w.'-]*(?: [A-Z][\w.'-]*){0,3})\s*:\s*(.*)$")
SPEAKER_HEADER = re.compile(r"^\s*([A-Z][\w.'-]*(?: [A-Z][\w.'-]*){0,3})\s+\d{1,2}:\d{2}(?::\d{2})?\s*$")


def read_transcript(path: Path) -> str:
    raw = path.read_bytes()
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return raw.decode("utf-16")
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("cp1252", errors="replace")


def precheck(text: str) -> Optional[str]:
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
    return ch.isalpha() or unicodedata.category(ch).startswith("M")


def content_hash(text: str) -> str:
    lines = text.replace("\r\n", "\n").replace("\r", "\n").strip().split("\n")
    canonical = "\n".join(line.rstrip() for line in lines)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", text.lower())).strip()


def utterances(text: str) -> List[str]:
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
