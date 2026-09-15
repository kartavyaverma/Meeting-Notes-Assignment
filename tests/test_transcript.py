import tempfile
import unittest
from pathlib import Path

from tests import TRANSCRIPTS
from meeting_notes.transcript import content_hash, precheck, read_transcript, utterances

KICKOFF = (TRANSCRIPTS / "sample-client-kickoff-brightpath.txt").read_text(encoding="utf-8")
DISCOVERY = (TRANSCRIPTS / "sample-sales-discovery-ridgeline.txt").read_text(encoding="utf-8")


class PrecheckTests(unittest.TestCase):
    def test_empty_file_is_rejected(self):
        self.assertEqual(precheck("  \n\t"), "file is empty")

    def test_mostly_symbols_is_rejected_as_garbled(self):
        self.assertIn("garbled", precheck("#$%^ 0x3F ]]]] 1101 @@ ~~ {{ }} ;;; ||| " * 30))

    def test_a_few_words_is_rejected_as_too_short(self):
        self.assertIn("too short", precheck("Priya: hi. Tom: hi, can't talk now, call you later."))

    def test_real_transcripts_pass(self):
        self.assertIsNone(precheck(KICKOFF))
        self.assertIsNone(precheck(DISCOVERY))

    def test_non_latin_script_is_not_mistaken_for_garbage(self):
        hindi = "प्रिया: आज की बैठक में हमने परियोजना के दो चरणों पर चर्चा की और सबने सहमति दी। " * 5
        self.assertIsNone(precheck(hindi))


class UtteranceTests(unittest.TestCase):
    def test_zoom_style_lines_carry_their_speaker(self):
        self.assertTrue(any(u.startswith("mark ellis") and "dig them out" in u for u in utterances(KICKOFF)))

    def test_otter_style_speaker_line_applies_to_the_text_below_it(self):
        self.assertTrue(any(u.startswith("priya nair") and "two case studies" in u for u in utterances(DISCOVERY)))


class ContentHashTests(unittest.TestCase):
    def test_line_endings_and_trailing_spaces_do_not_change_the_hash(self):
        self.assertEqual(content_hash("A: hi\r\nB: yo  \r\n"), content_hash("A: hi\nB: yo\n"))

    def test_different_content_gets_a_different_hash(self):
        self.assertNotEqual(content_hash("A: hi"), content_hash("A: bye"))


class ReadTranscriptTests(unittest.TestCase):
    def read(self, data: bytes) -> str:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp, "t.txt")
            path.write_bytes(data)
            return read_transcript(path)

    def test_utf16_export(self):
        self.assertEqual(self.read("Priya: hello".encode("utf-16")), "Priya: hello")

    def test_utf8_with_bom(self):
        self.assertEqual(self.read("﻿Priya: hello".encode("utf-8")), "Priya: hello")

    def test_windows_1252_fallback(self):
        self.assertEqual(self.read(b"Priya: caf\xe9"), "Priya: café")


if __name__ == "__main__":
    unittest.main()
