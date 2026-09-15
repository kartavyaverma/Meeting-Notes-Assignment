import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TRANSCRIPTS = ROOT / "transcripts"

if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))
