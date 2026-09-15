import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import tests  # noqa: F401  (puts src/ on the path)
from meeting_notes.config import DEFAULT_MODEL, ConfigError, Settings, load_dotenv

KEYS = ("GEMINI_API_KEY", "GEMINI_MODEL", "NOTION_TOKEN", "NOTION_DATABASE_ID",
        "GEMINI_INPUT_USD_PER_M", "GEMINI_OUTPUT_USD_PER_M")


def env(**values):
    """Patch the environment with every setting blank except the ones given."""
    patched = {key: "" for key in KEYS}
    patched.update(values)
    return mock.patch.dict(os.environ, patched)


class DotenvTests(unittest.TestCase):
    def test_loads_file_values_without_overriding_the_shell(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"NOTION_TOKEN": "from-shell"}):
            os.environ.pop("MEETING_NOTES_TEST_ONLY", None)
            Path(tmp, ".env").write_text(
                '# comment\nNOTION_TOKEN=from-file\nexport MEETING_NOTES_TEST_ONLY="quoted"\n', encoding="utf-8")
            loaded = load_dotenv(Path(tmp))
            self.assertEqual(loaded, Path(tmp).resolve() / ".env")
            self.assertEqual(os.environ["NOTION_TOKEN"], "from-shell")
            self.assertEqual(os.environ["MEETING_NOTES_TEST_ONLY"], "quoted")


class SettingsTests(unittest.TestCase):
    def test_unfilled_placeholders_count_as_missing(self):
        with env(GEMINI_API_KEY="your-gemini-api-key-here"):
            with self.assertRaises(ConfigError) as ctx:
                Settings.from_env(need_notion=False)
        self.assertIn("GEMINI_API_KEY", str(ctx.exception))

    def test_all_missing_keys_are_named_at_once(self):
        with env():
            with self.assertRaises(ConfigError) as ctx:
                Settings.from_env()
        for key in ("GEMINI_API_KEY", "NOTION_TOKEN", "NOTION_DATABASE_ID"):
            self.assertIn(key, str(ctx.exception))

    def test_dry_run_needs_only_the_gemini_key(self):
        with env(GEMINI_API_KEY="k"):
            settings = Settings.from_env(need_notion=False)
        self.assertEqual((settings.gemini_api_key, settings.gemini_model), ("k", DEFAULT_MODEL))

    def test_model_and_prices_come_from_the_environment(self):
        with env(GEMINI_API_KEY="k", GEMINI_MODEL="gemini-other", GEMINI_INPUT_USD_PER_M="0.75",
                 GEMINI_OUTPUT_USD_PER_M="3.75"):
            settings = Settings.from_env(need_notion=False)
        self.assertEqual((settings.gemini_model, settings.input_usd_per_m, settings.output_usd_per_m),
                         ("gemini-other", 0.75, 3.75))

    def test_non_numeric_price_is_rejected(self):
        with env(GEMINI_API_KEY="k", GEMINI_INPUT_USD_PER_M="cheap"):
            with self.assertRaises(ConfigError):
                Settings.from_env(need_notion=False)

    def test_database_id_copied_with_dashes_is_accepted(self):
        with env(NOTION_TOKEN="t", NOTION_DATABASE_ID="3dc6a28a-9984-8028-9cb2-dc4b4273e15c"):
            settings = Settings.from_env(need_gemini=False)
        self.assertEqual(settings.notion_database_id, "3dc6a28a998480289cb2dc4b4273e15c")


if __name__ == "__main__":
    unittest.main()
