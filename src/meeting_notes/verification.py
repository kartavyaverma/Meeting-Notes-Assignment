from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List

from .transcript import normalize, utterances

MIN_QUOTE_WORDS = 3


def verify_action_items(notes: Dict[str, Any], text: str) -> None:
    whole = normalize(text)
    said = utterances(text)
    for item in notes["action_items"]:
        item["verify"] = _reasons(item, whole, said)


def _reasons(item: Dict[str, Any], whole: str, said: List[str]) -> List[str]:
    owner = item["owner"].strip()
    owner_words = normalize(owner).split()
    quote = normalize(item["evidence"])
    reasons: List[str] = []

    if not owner_words or item["owner_status"] == "unassigned":
        reasons.append("no owner named in the transcript")
    elif item["owner_status"] == "implied":
        reasons.append(f"owner inferred, not stated (best guess: {owner})")

    if not quote or quote not in whole:
        reasons.append("supporting quote not found in the transcript")
    elif len(quote.split()) < MIN_QUOTE_WORDS:
        reasons.append("supporting quote too short to verify")
    elif owner_words:
        first_name = re.escape(owner_words[0])
        lines = [u for u in said if quote in u]
        if lines and not any(re.search(rf"\b{first_name}\b", u) for u in lines):
            reasons.append(f"the quote isn't from or addressed to {owner}")

    if item["soft_commitment"]:
        reasons.append("soft commitment, may not happen")
    return reasons


def fix_date(notes: Dict[str, Any]) -> None:
    try:
        datetime.strptime(notes["date"], "%Y-%m-%d")
    except ValueError:
        if notes["date"]:
            notes["assumptions"].append(f"Date \"{notes['date']}\" wasn't a clear calendar date, so it was left blank.")
        else:
            notes["assumptions"].append("No meeting date was stated in the transcript, so Date was left blank.")
        notes["date"] = ""
