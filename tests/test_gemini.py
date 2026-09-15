import json
import unittest

import tests
from meeting_notes.api import ApiError
from meeting_notes.config import Settings
from meeting_notes.gemini import GeminiClient, cost_usd, normalize_notes, parse_response
from tests.fakes import SETTINGS, FakeHttp, gemini_response, meeting_notes


class NormalizeNotesTests(unittest.TestCase):
    def test_missing_fields_get_fresh_defaults_every_time(self):
        first = normalize_notes({})
        first["assumptions"].append("changed by the first transcript")
        second = normalize_notes({})
        self.assertEqual(second["assumptions"], [])
        self.assertFalse(second["is_meeting_transcript"])
        self.assertEqual(second["title"], "Untitled meeting")

    def test_malformed_entries_are_dropped_and_unknown_status_is_distrusted(self):
        notes = normalize_notes({
            "action_items": ["not an object", {"task": ""},
                             {"task": "Send the deck", "owner": None, "owner_status": "certain", "soft_commitment": "yes"}],
            "attendees": [{"name": "Ana"}, {"role": "no name"}],
            "decisions": ["Ship it", 3, "   "],
        })
        self.assertEqual(len(notes["action_items"]), 1)
        item = notes["action_items"][0]
        self.assertEqual((item["owner"], item["owner_status"], item["soft_commitment"]), ("", "unassigned", False))
        self.assertEqual(notes["attendees"], [{"name": "Ana", "role": ""}])
        self.assertEqual(notes["decisions"], ["Ship it"])


class ExtractTests(unittest.TestCase):
    def client(self, *responses, settings=SETTINGS):
        self.http = FakeHttp(*responses)
        self.waits = []
        self.messages = []
        return GeminiClient(settings, http=self.http, sleep=self.waits.append, notify=self.messages.append)

    def test_returns_notes_and_usage_from_one_request(self):
        notes, usage = self.client(gemini_response(meeting_notes())).extract("transcript", "a.txt")
        self.assertEqual(notes["title"], "Kickoff")
        self.assertEqual(usage["promptTokenCount"], 1000)
        call = self.http.calls[0]
        self.assertTrue(call["url"].endswith("/gemini-3.8-flash:generateContent"))
        self.assertEqual(call["headers"]["x-goog-api-key"], "test-gemini-key")
        self.assertEqual(call["body"]["generationConfig"]["thinkingConfig"], {"thinkingLevel": "low"})

    def test_model_can_be_changed_through_settings(self):
        client = self.client(gemini_response(meeting_notes()), settings=Settings(gemini_api_key="k", gemini_model="gemini-x"))
        client.extract("transcript", "a.txt")
        self.assertTrue(self.http.calls[0]["url"].endswith("/gemini-x:generateContent"))

    def test_overload_retries_twice_with_spaced_waits_then_gives_up(self):
        busy = ApiError(503, "This model is currently experiencing high demand.")
        client = self.client(busy, busy, busy)
        with self.assertRaises(ApiError) as ctx:
            client.extract("transcript", "a.txt")
        self.assertEqual((ctx.exception.status, ctx.exception.service), (503, "Gemini"))
        self.assertEqual(len(self.http.calls), 3)
        self.assertEqual(self.waits, [20, 40])
        self.assertEqual(len(self.messages), 2)

    def test_recovers_when_a_retry_succeeds(self):
        client = self.client(ApiError(503, "busy"), gemini_response(meeting_notes()))
        notes, _ = client.extract("transcript", "a.txt")
        self.assertEqual(notes["title"], "Kickoff")
        self.assertEqual(self.waits, [20])

    def test_quota_exhaustion_is_not_retried(self):
        client = self.client(ApiError(429, "You exceeded your current quota"))
        with self.assertRaises(ApiError) as ctx:
            client.extract("transcript", "a.txt")
        self.assertIn("quota used up", str(ctx.exception))
        self.assertEqual((len(self.http.calls), self.waits), (1, []))

    def test_unsupported_thinking_setting_is_dropped_and_retried(self):
        client = self.client(ApiError(400, "thinkingLevel is not supported for this model"),
                             gemini_response(meeting_notes()))
        client.extract("transcript", "a.txt")
        self.assertIn("thinkingConfig", self.http.calls[0]["body"]["generationConfig"])
        self.assertNotIn("thinkingConfig", self.http.calls[1]["body"]["generationConfig"])

    def test_unknown_model_points_at_the_setting(self):
        with self.assertRaises(ApiError) as ctx:
            self.client(ApiError(404, "models/gemini-x is not found")).extract("transcript", "a.txt")
        self.assertIn("GEMINI_MODEL", str(ctx.exception))


class ParseResponseTests(unittest.TestCase):
    def test_truncated_answer_is_an_error(self):
        with self.assertRaises(ApiError) as ctx:
            parse_response(gemini_response(meeting_notes(), finish="MAX_TOKENS"))
        self.assertIn("MAX_TOKENS", str(ctx.exception))

    def test_invalid_json_is_an_error(self):
        response = {"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": "not json"}]}}]}
        with self.assertRaises(ApiError):
            parse_response(response)

    def test_blocked_prompt_is_an_error(self):
        with self.assertRaises(ApiError) as ctx:
            parse_response({"promptFeedback": {"blockReason": "SAFETY"}})
        self.assertIn("SAFETY", str(ctx.exception))

    def test_thought_parts_are_ignored(self):
        response = {"candidates": [{"finishReason": "STOP", "content": {"parts": [
            {"text": "let me think about owners...", "thought": True},
            {"text": json.dumps(meeting_notes())},
        ]}}]}
        self.assertEqual(parse_response(response)["title"], "Kickoff")


class CostTests(unittest.TestCase):
    def test_cost_matches_the_recorded_run(self):
        usage = {"promptTokenCount": 2324, "candidatesTokenCount": 1064, "thoughtsTokenCount": 0}
        self.assertAlmostEqual(cost_usd(usage, SETTINGS), 0.005733, places=6)

    def test_thinking_tokens_bill_at_the_output_price(self):
        usage = {"promptTokenCount": 0, "candidatesTokenCount": 0, "thoughtsTokenCount": 1000}
        self.assertAlmostEqual(cost_usd(usage, SETTINGS), 0.00375)

    def test_no_prices_means_no_cost_shown(self):
        self.assertIsNone(cost_usd({"promptTokenCount": 10}, Settings()))


if __name__ == "__main__":
    unittest.main()
