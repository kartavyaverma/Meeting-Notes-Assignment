import unittest

from tests import TRANSCRIPTS
from meeting_notes.verification import fix_date, verify_action_items

KICKOFF = "sample-client-kickoff-brightpath.txt"
DISCOVERY = "sample-sales-discovery-ridgeline.txt"


def reasons(transcript, owner, quote, status="explicit", soft=False):
    text = (TRANSCRIPTS / transcript).read_text(encoding="utf-8")
    notes = {"action_items": [{"task": "-", "owner": owner, "owner_status": status, "evidence": quote,
                               "due": "", "soft_commitment": soft}]}
    verify_action_items(notes, text)
    return notes["action_items"][0]["verify"]


class OwnerCheckTests(unittest.TestCase):
    def test_correct_owner_passes(self):
        self.assertEqual(reasons(KICKOFF, "Mark Ellis", "Fine, I'll dig them out and send them over this week."), [])
        self.assertEqual(reasons(KICKOFF, "Daniel Okafor",
                                 "I'll submit the Dentrix developer access request by Friday"), [])

    def test_person_who_was_asked_first_is_caught(self):
        self.assertIn("the quote isn't from or addressed to Sarah Chen",
                      reasons(KICKOFF, "Sarah Chen", "Fine, I'll dig them out and send them over this week."))

    def test_person_who_handed_the_task_off_is_caught(self):
        self.assertIn("the quote isn't from or addressed to Daniel Okafor",
                      reasons(KICKOFF, "Daniel Okafor", "I'll ask Aisha today and get her started on it."))

    def test_invented_quote_is_caught(self):
        self.assertIn("supporting quote not found in the transcript",
                      reasons(KICKOFF, "Daniel Okafor", "I'll send the signed contract back tomorrow morning"))

    def test_otter_format_is_checked_the_same_way(self):
        quote = "I'll send you two case studies from similar logistics projects by Thursday"
        self.assertEqual(reasons(DISCOVERY, "Priya Nair", quote), [])
        self.assertIn("the quote isn't from or addressed to Tom Becker", reasons(DISCOVERY, "Tom Becker", quote))

    def test_unassigned_item_is_flagged(self):
        self.assertEqual(reasons(KICKOFF, "", "someone should probably loop in legal about the data side",
                                 status="unassigned"), ["no owner named in the transcript"])

    def test_implied_owner_is_flagged_with_the_best_guess(self):
        self.assertEqual(reasons(KICKOFF, "Priya Nair", "We'll get the revised quote over to you with that as an option",
                                 status="implied"), ["owner inferred, not stated (best guess: Priya Nair)"])

    def test_soft_commitment_is_flagged(self):
        self.assertEqual(reasons(KICKOFF, "Mark Ellis", "I'll try to get those over to you, but no promises this week",
                                 soft=True), ["soft commitment, may not happen"])

    def test_quote_too_short_to_prove_anything_is_flagged(self):
        self.assertIn("supporting quote too short to verify", reasons(KICKOFF, "Daniel Okafor", "Perfect."))

    def test_owner_with_no_real_name_counts_as_missing(self):
        self.assertIn("no owner named in the transcript",
                      reasons(KICKOFF, "—", "I'll submit the Dentrix developer access request by Friday"))


class FixDateTests(unittest.TestCase):
    def test_valid_date_is_kept(self):
        notes = {"date": "2026-09-10", "assumptions": []}
        fix_date(notes)
        self.assertEqual(notes, {"date": "2026-09-10", "assumptions": []})

    def test_missing_date_is_recorded_as_an_assumption(self):
        notes = {"date": "", "assumptions": []}
        fix_date(notes)
        self.assertIn("No meeting date was stated", notes["assumptions"][0])

    def test_vague_date_is_blanked_rather_than_guessed(self):
        notes = {"date": "next Tuesday", "assumptions": []}
        fix_date(notes)
        self.assertEqual(notes["date"], "")
        self.assertIn("next Tuesday", notes["assumptions"][0])


if __name__ == "__main__":
    unittest.main()
