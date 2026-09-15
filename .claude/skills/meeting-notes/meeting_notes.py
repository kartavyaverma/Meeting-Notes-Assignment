#!/usr/bin/env python3
"""Entry point for the /meeting-notes skill.

The implementation lives in src/meeting_notes/. This file only makes that package importable
without installing anything, so this command works from the project root:

    python .claude/skills/meeting-notes/meeting_notes.py transcripts/
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

from meeting_notes.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
