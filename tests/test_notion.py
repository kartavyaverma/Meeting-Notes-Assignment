import unittest
from datetime import date

import tests
from meeting_notes.api import ApiError
from meeting_notes.config import ConfigError
from meeting_notes.notion import REQUIRED_COLUMNS, NotionClient, page_blocks, rich_text
from tests.fakes import SETTINGS, FakeHttp, meeting_notes

TODAY = date(2026, 9, 15)


def columns_response(columns):
    return {"properties": {name: {"type": kind} for name, kind in columns.items()}}


def text_of(block):
    return "".join(part["text"]["content"] for part in block[block["type"]]["rich_text"])


def notes_with_flags(*flag_lists, **overrides):
    base = meeting_notes()["action_items"][0]
    return meeting_notes(action_items=[dict(base, verify=list(flags)) for flags in flag_lists], **overrides)


class PageBlocksTests(unittest.TestCase):
    def test_callout_counts_the_items_needing_a_check(self):
        notes = notes_with_flags([], ["no owner named in the transcript"], ["soft commitment, may not happen"])
        callout = page_blocks(notes, "a.txt", {}, "gemini-test", TODAY)[0]
        self.assertEqual(callout["type"], "callout")
        self.assertIn("2 of 3 action items need a human check", text_of(callout))
        self.assertEqual(callout["callout"]["color"], "yellow_background")

    def test_green_callout_when_every_owner_is_confirmed(self):
        callout = page_blocks(notes_with_flags([]), "a.txt", {}, "gemini-test", TODAY)[0]
        self.assertEqual(callout["callout"]["color"], "green_background")

    def test_action_table_has_a_header_and_a_row_per_item(self):
        notes = notes_with_flags([], ["no owner named in the transcript"])
        table = next(b for b in page_blocks(notes, "a.txt", {}, "gemini-test", TODAY) if b["type"] == "table")
        rows = table["table"]["children"]
        self.assertEqual((table["table"]["table_width"], len(rows)), (5, 3))
        status = "".join(part["text"]["content"] for part in rows[2]["table_row"]["cells"][3])
        self.assertEqual(status, "⚠️ Please verify: no owner named in the transcript")

    def test_meeting_without_action_items_says_so(self):
        blocks = page_blocks(meeting_notes(action_items=[]), "a.txt", {}, "gemini-test", TODAY)
        self.assertIn("No action items.", [text_of(b) for b in blocks if b["type"] == "paragraph"])
        self.assertNotEqual(blocks[0]["type"], "callout")

    def test_worst_case_page_stays_within_notion_request_limits(self):
        many = [f"entry {n}" for n in range(200)]
        notes = notes_with_flags(*([[]] * 200), decisions=many, assumptions=many,
                                 attendees=[{"name": f"Person {n}", "role": ""} for n in range(200)])
        blocks = page_blocks(notes, "a.txt", {}, "gemini-test", TODAY)
        self.assertLessEqual(len(blocks), 100)
        table = next(b for b in blocks if b["type"] == "table")
        self.assertLessEqual(len(table["table"]["children"]), 100)

    def test_long_text_is_split_into_notion_sized_chunks(self):
        self.assertEqual([len(part["text"]["content"]) for part in rich_text("x" * 4500)], [2000, 2000, 500])

    def test_footer_names_the_source_model_date_and_tokens(self):
        usage = {"promptTokenCount": 10, "candidatesTokenCount": 5, "thoughtsTokenCount": 0}
        footer = text_of(page_blocks(notes_with_flags([]), "a.txt", usage, "gemini-test", TODAY)[-1])
        for expected in ("a.txt", "gemini-test", "2026-09-15", "10 in / 5 out / 0 thinking tokens"):
            self.assertIn(expected, footer)


class NotionClientTests(unittest.TestCase):
    def client(self, *responses):
        self.http = FakeHttp(*responses)
        return NotionClient(SETTINGS, http=self.http)

    def test_check_database_returns_the_title_column(self):
        client = self.client(columns_response({"Meeting": "title", **REQUIRED_COLUMNS}))
        self.assertEqual(client.check_database(), "Meeting")

    def test_check_database_names_missing_columns_and_the_fix(self):
        client = self.client(columns_response({"Name": "title", "Date": "date", "Source": "rich_text"}))
        with self.assertRaises(ConfigError) as ctx:
            client.check_database()
        for expected in ("Attendees", "Needs review", "Content hash", "--init-db"):
            self.assertIn(expected, str(ctx.exception))

    def test_init_database_adds_only_the_missing_columns(self):
        client = self.client(columns_response({"Name": "title", "Date": "date"}), {})
        added = client.init_database()
        self.assertEqual(sorted(added), ["Attendees", "Content hash", "Needs review", "Source"])
        update = self.http.calls[1]
        self.assertEqual(update["method"], "PATCH")
        self.assertEqual(update["body"]["properties"]["Needs review"], {"checkbox": {}})
        self.assertNotIn("Date", update["body"]["properties"])

    def test_init_database_does_nothing_when_already_set_up(self):
        client = self.client(columns_response({"Name": "title", **REQUIRED_COLUMNS}))
        self.assertEqual(client.init_database(), [])
        self.assertEqual(len(self.http.calls), 1)

    def test_init_database_never_changes_an_existing_column_type(self):
        client = self.client(columns_response({"Name": "title", "Date": "rich_text"}))
        with self.assertRaises(ConfigError):
            client.init_database()
        self.assertEqual(len(self.http.calls), 1)

    def test_duplicate_is_found_by_content_hash(self):
        client = self.client({"results": [{"url": "https://notion.test/page"}]})
        self.assertEqual(client.find_existing("a.txt", "abc"), "https://notion.test/page")
        self.assertEqual(len(self.http.calls), 1)

    def test_page_imported_before_hashes_existed_is_matched_by_filename(self):
        client = self.client({"results": []}, {"results": [{"url": "https://notion.test/old"}]})
        self.assertEqual(client.find_existing("a.txt", "abc"), "https://notion.test/old")
        self.assertIn({"property": "Content hash", "rich_text": {"is_empty": True}},
                      self.http.calls[1]["body"]["filter"]["and"])

    def test_same_filename_with_different_content_is_not_a_duplicate(self):
        client = self.client({"results": []}, {"results": []})
        self.assertIsNone(client.find_existing("a.txt", "abc"))

    def test_rejected_token_explains_the_fix(self):
        with self.assertRaises(ApiError) as ctx:
            self.client(ApiError(401, "API token is invalid.")).check_database()
        self.assertIn("NOTION_TOKEN", str(ctx.exception))

    def test_unshared_database_explains_the_fix(self):
        with self.assertRaises(ApiError) as ctx:
            self.client(ApiError(404, "Could not find database")).check_database()
        self.assertIn("Connections", str(ctx.exception))

    def test_create_page_writes_review_flag_and_hash_and_skips_a_blank_date(self):
        client = self.client({"url": "https://notion.test/new"})
        notes = notes_with_flags(["soft commitment, may not happen"], date="")
        url = client.create_page(notes, "a.txt", "abc", {}, "Name", "gemini-test", today=TODAY)
        self.assertEqual(url, "https://notion.test/new")
        body = self.http.calls[0]["body"]
        self.assertEqual(body["parent"], {"database_id": "db123"})
        self.assertTrue(body["properties"]["Needs review"]["checkbox"])
        self.assertEqual(body["properties"]["Content hash"]["rich_text"][0]["text"]["content"], "abc")
        self.assertNotIn("Date", body["properties"])


if __name__ == "__main__":
    unittest.main()
