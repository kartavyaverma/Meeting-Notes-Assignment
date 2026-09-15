import os
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest import mock

from tests import TRANSCRIPTS
from meeting_notes import cli
from meeting_notes.api import ApiError
from tests.fakes import SETTINGS, meeting_notes

KICKOFF_TEXT = (TRANSCRIPTS / "sample-client-kickoff-brightpath.txt").read_text(encoding="utf-8")
USAGE = {"promptTokenCount": 2000, "candidatesTokenCount": 1000, "thoughtsTokenCount": 0}


class FakeGemini:
    model = "gemini-test"
    settings = SETTINGS

    def __init__(self, *outcomes):
        self.outcomes = list(outcomes)
        self.calls = []

    def extract(self, text, source):
        self.calls.append(source)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome, USAGE


class FakeNotion:
    def __init__(self, existing=None, create_error=None):
        self.existing = existing or {}
        self.create_error = create_error
        self.created = []

    def check_database(self):
        return "Name"

    def find_existing(self, source, digest):
        return self.existing.get(source)

    def create_page(self, notes, source, digest, usage, title_column, model):
        if self.create_error:
            raise self.create_error
        self.created.append(source)
        return f"https://notion.test/{source}"


class BatchTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.folder = Path(tmp.name)
        self.lines = []

    def transcripts(self, *names, text=KICKOFF_TEXT):
        paths = []
        for name in names:
            path = self.folder / name
            path.write_text(text, encoding="utf-8")
            paths.append(path)
        return paths

    def run_batch(self, files, gemini, notion, **options):
        return cli.Runner(gemini, notion, out=self.lines.append, **options).run(files)

    def test_creates_one_page_per_transcript(self):
        notion = FakeNotion()
        results = self.run_batch(self.transcripts("a.txt", "b.txt"), FakeGemini(meeting_notes(), meeting_notes()), notion)
        self.assertEqual([r.status for r in results], ["created", "created"])
        self.assertEqual(notion.created, ["a.txt", "b.txt"])

    def test_gemini_overload_stops_the_batch_instead_of_burning_quota(self):
        gemini = FakeGemini(ApiError(503, "high demand", "Gemini"))
        results = self.run_batch(self.transcripts("a.txt", "b.txt", "c.txt"), gemini, FakeNotion())
        self.assertEqual([r.status for r in results], ["failed", "not run", "not run"])
        self.assertEqual(gemini.calls, ["a.txt"])

    def test_a_notion_failure_does_not_stop_the_batch(self):
        gemini = FakeGemini(meeting_notes(), meeting_notes())
        results = self.run_batch(self.transcripts("a.txt", "b.txt"), gemini,
                                 FakeNotion(create_error=ApiError(500, "internal error", "Notion")))
        self.assertEqual([r.status for r in results], ["failed", "failed"])
        self.assertEqual(len(gemini.calls), 2)

    def test_already_imported_transcript_is_skipped_before_calling_gemini(self):
        gemini = FakeGemini()
        results = self.run_batch(self.transcripts("a.txt"), gemini, FakeNotion(existing={"a.txt": "https://notion.test/old"}))
        self.assertEqual(results[0].status, "skipped")
        self.assertIn("already in Notion", results[0].detail)
        self.assertEqual(gemini.calls, [])

    def test_force_imports_an_already_imported_transcript(self):
        results = self.run_batch(self.transcripts("a.txt"), FakeGemini(meeting_notes()),
                                 FakeNotion(existing={"a.txt": "https://notion.test/old"}), force=True)
        self.assertEqual(results[0].status, "created")

    def test_text_that_is_not_a_meeting_is_skipped_and_nothing_is_written(self):
        notion = FakeNotion()
        notes = meeting_notes(is_meeting_transcript=False, rejection_reason="a baking recipe")
        results = self.run_batch(self.transcripts("a.txt"), FakeGemini(notes), notion)
        self.assertEqual(results[0].status, "skipped")
        self.assertIn("a baking recipe", results[0].detail)
        self.assertEqual(notion.created, [])

    def test_garbled_file_is_skipped_without_any_api_call(self):
        gemini = FakeGemini()
        results = self.run_batch(self.transcripts("a.txt", text="#$%^ ]]]] @@ ;;; " * 40), gemini, FakeNotion())
        self.assertEqual(results[0].status, "skipped")
        self.assertEqual(gemini.calls, [])

    def test_dry_run_works_without_notion(self):
        results = self.run_batch(self.transcripts("a.txt"), FakeGemini(meeting_notes()), None, dry_run=True)
        self.assertEqual(results[0].status, "dry run")

    def test_unverified_owner_is_printed_with_its_reason(self):
        item = {"task": "Loop in legal", "owner": "", "owner_status": "unassigned",
                "evidence": "someone should probably loop in legal about the data side", "due": "",
                "soft_commitment": False}
        self.run_batch(self.transcripts("a.txt"), FakeGemini(meeting_notes(action_items=[item])), FakeNotion())
        self.assertIn("         please verify: no owner named in the transcript", self.lines)

    def test_cost_is_printed_when_prices_are_configured(self):
        self.run_batch(self.transcripts("a.txt"), FakeGemini(meeting_notes()), FakeNotion())
        self.assertTrue(any(line.endswith("~$0.0053") for line in self.lines))


class CollectFilesTests(unittest.TestCase):
    def test_folders_expand_to_sorted_txt_files_without_duplicates(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            for name in ("b.txt", "a.txt", "notes.md"):
                (folder / name).write_text("x", encoding="utf-8")
            files = cli.collect_files([str(folder), str(folder / "a.txt")])
        self.assertEqual([f.name for f in files], ["a.txt", "b.txt"])

    def test_missing_path_is_a_setup_error(self):
        with self.assertRaises(cli.ConfigError):
            cli.collect_files(["does-not-exist.txt"])


class MainTests(unittest.TestCase):
    def setUp(self):
        no_dotenv = mock.patch.object(cli, "load_dotenv", lambda: None)
        no_dotenv.start()
        self.addCleanup(no_dotenv.stop)
        blank_env = mock.patch.dict(os.environ, {key: "" for key in (
            "GEMINI_API_KEY", "GEMINI_MODEL", "NOTION_TOKEN", "NOTION_DATABASE_ID",
            "GEMINI_INPUT_USD_PER_M", "GEMINI_OUTPUT_USD_PER_M")})
        blank_env.start()
        self.addCleanup(blank_env.stop)

    def run_main(self, *argv):
        stderr = StringIO()
        with mock.patch("sys.stderr", stderr), mock.patch("sys.stdout", StringIO()):
            code = cli.main(list(argv))
        return code, stderr.getvalue()

    def test_missing_keys_exit_with_a_setup_error(self):
        code, stderr = self.run_main(str(TRANSCRIPTS / "sample-sales-discovery-ridgeline.txt"))
        self.assertEqual(code, cli.EXIT_CONFIG)
        self.assertIn("GEMINI_API_KEY", stderr)

    def test_missing_transcript_exits_with_a_setup_error(self):
        code, stderr = self.run_main("does-not-exist.txt")
        self.assertEqual(code, cli.EXIT_CONFIG)
        self.assertIn("Not found", stderr)

    def test_no_arguments_is_a_usage_error(self):
        with self.assertRaises(SystemExit) as ctx:
            self.run_main()
        self.assertEqual(ctx.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
