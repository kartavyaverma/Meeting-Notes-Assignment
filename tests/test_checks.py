"""Offline checks for the safeguards in meeting_notes.py. No API calls, no quota used.

Run from the project root:  python tests/test_checks.py
"""
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("meeting_notes", ROOT / ".claude/skills/meeting-notes/meeting_notes.py")
mn = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mn)
sys.stdout.reconfigure(encoding="utf-8")

KICKOFF = "sample-client-kickoff-brightpath.txt"   # Zoom style: "[00:01:02] Name: text"
DISCOVERY = "sample-sales-discovery-ridgeline.txt" # Otter style: "Name  0:12" then text
failures = 0


def expect(label, ok, detail=""):
    global failures
    failures += not ok
    print(f"{'PASS' if ok else 'FAIL'}  {label}" + (f"\n        -> {detail}" if detail else ""))


def verify_reasons(transcript, owner, quote):
    """Run the owner check on one action item the model claims is 'explicit'."""
    text = (ROOT / "transcripts" / transcript).read_text(encoding="utf-8")
    notes = {"action_items": [{"task": "-", "owner": owner, "owner_status": "explicit", "evidence": quote,
                               "due": "", "soft_commitment": False}]}
    mn.check_owners(notes, text)
    return notes["action_items"][0]["verify"]


def owner_case(label, transcript, owner, quote, should_flag):
    reasons = verify_reasons(transcript, owner, quote)
    expect(label, bool(reasons) == should_flag, "; ".join(reasons))


print("Owner check (the model claims every owner below is 'explicit'):")
owner_case("correct owner passes: Mark owns the brand guidelines", KICKOFF, "Mark Ellis",
           "Fine, I'll dig them out and send them over this week.", False)
owner_case("wrong owner caught: Sarah was asked first, but Mark took it", KICKOFF, "Sarah Chen",
           "Fine, I'll dig them out and send them over this week.", True)
owner_case("wrong owner caught: Daniel handed the sitemap off", KICKOFF, "Daniel Okafor",
           "I'll ask Aisha today and get her started on it.", True)
owner_case("correct owner passes: Daniel submits the Dentrix request", KICKOFF, "Daniel Okafor",
           "I'll submit the Dentrix developer access request by Friday", False)
owner_case("invented quote caught", KICKOFF, "Daniel Okafor",
           "I'll send the signed contract back tomorrow morning", True)
owner_case("correct owner passes (Otter format): Priya sends case studies", DISCOVERY, "Priya Nair",
           "I'll send you two case studies from similar logistics projects by Thursday", False)
owner_case("wrong owner caught (Otter format): Tom didn't promise case studies", DISCOVERY, "Tom Becker",
           "I'll send you two case studies from similar logistics projects by Thursday", True)

print("\nInput checks (these run before any API call):")
for label, text, want in [
    ("empty file is skipped", "   \n", "file is empty"),
    ("garbled file is skipped", "#$%^ 0x3F ]]]] 1101 @@ ~~ {{ }} ;;; ||| " * 30, "mostly non-letter"),
    ("too-short file is skipped", "Priya: hi. Tom: hi, can't talk now, call you later.", "only"),
]:
    got = mn.precheck(text)
    expect(label, bool(got) and got.startswith(want), got)
real = (ROOT / "transcripts" / KICKOFF).read_text(encoding="utf-8")
expect("a real transcript passes the input checks", mn.precheck(real) is None)

print(f"\n{'All checks passed.' if not failures else f'{failures} check(s) failed.'}")
sys.exit(1 if failures else 0)
