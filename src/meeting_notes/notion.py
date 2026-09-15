from __future__ import annotations

from datetime import date
from typing import Any, Callable, Dict, List, Optional

from .api import ApiError, request_json
from .config import ConfigError, Settings

API_BASE = "https://api.notion.com/v1"
API_VERSION = "2022-06-28"
TEXT_LIMIT = 2000
MAX_TEXT_CHUNKS = 100
LIST_LIMIT = 25

REQUIRED_COLUMNS = {
    "Date": "date",
    "Attendees": "rich_text",
    "Needs review": "checkbox",
    "Source": "rich_text",
    "Content hash": "rich_text",
}

Block = Dict[str, Any]


class NotionClient:
    def __init__(self, settings: Settings, http: Callable[..., Dict[str, Any]] = request_json) -> None:
        self.settings = settings
        self._http = http

    @property
    def _database(self) -> str:
        return self.settings.notion_database_id

    def _call(self, method: str, path: str, body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        headers = {"Authorization": f"Bearer {self.settings.notion_token}", "Notion-Version": API_VERSION}
        try:
            return self._http(method, API_BASE + path, headers, body)
        except ApiError as e:
            if e.status == 401:
                raise ApiError(401, "the access token was rejected. Copy NOTION_TOKEN again from "
                                    "Developer tools -> Connections.", "Notion") from None
            if e.status == 404:
                raise ApiError(404, "the database isn't visible. Check NOTION_DATABASE_ID, and add the "
                                    "connection to the database (the ... menu -> Connections).", "Notion") from None
            raise ApiError(e.status, e.message, "Notion") from None

    def columns(self) -> Dict[str, str]:
        database = self._call("GET", f"/databases/{self._database}")
        return {name: prop["type"] for name, prop in database["properties"].items()}

    def check_database(self) -> str:
        columns = self.columns()
        problems = []
        for name, kind in REQUIRED_COLUMNS.items():
            actual = columns.get(name)
            if actual is None:
                problems.append(f"'{name}' is missing")
            elif actual != kind:
                problems.append(f"'{name}' is {actual}, expected {kind}")
        if problems:
            raise ConfigError(f"The Notion database isn't set up: {'; '.join(problems)}. "
                              "Run the skill script with --init-db to add missing columns.")
        return _title_column(columns)

    def init_database(self) -> List[str]:
        columns = self.columns()
        wrong = [f"'{name}' is {columns[name]}, expected {kind}"
                 for name, kind in REQUIRED_COLUMNS.items() if name in columns and columns[name] != kind]
        if wrong:
            raise ConfigError(f"Can't set up the database automatically: {'; '.join(wrong)}. "
                              "Rename or delete those columns in Notion first.")
        missing = [name for name in REQUIRED_COLUMNS if name not in columns]
        if missing:
            properties = {name: {REQUIRED_COLUMNS[name]: {}} for name in missing}
            self._call("PATCH", f"/databases/{self._database}", {"properties": properties})
        return missing

    def find_existing(self, source: str, digest: str) -> Optional[str]:
        url = self._first_match({"property": "Content hash", "rich_text": {"equals": digest}})
        if url:
            return url
        return self._first_match({"and": [
            {"property": "Source", "rich_text": {"equals": source}},
            {"property": "Content hash", "rich_text": {"is_empty": True}},
        ]})

    def _first_match(self, query_filter: Dict[str, Any]) -> Optional[str]:
        result = self._call("POST", f"/databases/{self._database}/query", {"filter": query_filter, "page_size": 1})
        pages = result.get("results") or []
        return pages[0].get("url") if pages else None

    def create_page(
        self,
        notes: Dict[str, Any],
        source: str,
        digest: str,
        usage: Dict[str, int],
        title_column: str,
        model: str,
        today: Optional[date] = None,
    ) -> str:
        properties: Dict[str, Any] = {
            title_column: {"title": rich_text(notes["title"])},
            "Attendees": {"rich_text": rich_text(", ".join(a["name"] for a in notes["attendees"]))},
            "Needs review": {"checkbox": any(item["verify"] for item in notes["action_items"])},
            "Source": {"rich_text": rich_text(source)},
            "Content hash": {"rich_text": rich_text(digest)},
        }
        if notes["date"]:
            properties["Date"] = {"date": {"start": notes["date"]}}
        page = self._call("POST", "/pages", {
            "parent": {"database_id": self._database},
            "properties": properties,
            "children": page_blocks(notes, source, usage, model, today),
        })
        return page.get("url", "")


def _title_column(columns: Dict[str, str]) -> str:
    for name, kind in columns.items():
        if kind == "title":
            return name
    raise ConfigError("The Notion database has no title column.")


def rich_text(text: Any) -> List[Dict[str, Any]]:
    text = str(text or "")
    chunks = [text[i:i + TEXT_LIMIT] for i in range(0, len(text), TEXT_LIMIT)][:MAX_TEXT_CHUNKS]
    return [{"type": "text", "text": {"content": chunk}} for chunk in chunks]


def block(kind: str, text: str, **extra: Any) -> Block:
    return {"object": "block", "type": kind, kind: {"rich_text": rich_text(text), **extra}}


def status_text(item: Dict[str, Any]) -> str:
    return "⚠️ Please verify: " + "; ".join(item["verify"]) if item["verify"] else "✅ Owner named"


def _bullets(items: List[str], empty: str) -> List[Block]:
    if not items:
        return [block("paragraph", empty)]
    blocks = [block("bulleted_list_item", item) for item in items[:LIST_LIMIT]]
    if len(items) > LIST_LIMIT:
        blocks.append(block("paragraph", f"...and {len(items) - LIST_LIMIT} more (see transcript)."))
    return blocks


def page_blocks(
    notes: Dict[str, Any],
    source: str,
    usage: Dict[str, int],
    model: str,
    today: Optional[date] = None,
) -> List[Block]:
    items = notes["action_items"]
    flagged = [item for item in items if item["verify"]]
    blocks: List[Block] = []

    if flagged:
        blocks.append(block("callout", f"{len(flagged)} of {len(items)} action items need a human check before "
                                       "anyone acts on them. See the Status column.",
                            icon={"type": "emoji", "emoji": "⚠️"}, color="yellow_background"))
    elif items:
        blocks.append(block("callout", "Every action item has an owner named in the transcript.",
                            icon={"type": "emoji", "emoji": "✅"}, color="green_background"))

    blocks += [block("heading_2", "Summary"), block("paragraph", notes["summary"] or "No summary.")]
    blocks.append(block("heading_2", "Attendees"))
    blocks += _bullets([a["name"] + (f" ({a['role']})" if a["role"] else "") for a in notes["attendees"]],
                       "No attendees identified.")
    blocks.append(block("heading_2", "Decisions"))
    blocks += _bullets(notes["decisions"], "No decisions recorded.")

    blocks.append(block("heading_2", "Action items"))
    if items:
        rows = [["Task", "Owner", "Due", "Status", "From the transcript"]]
        rows += [[item["task"], item["owner"] or "Unassigned", item["due"] or "—", status_text(item),
                  f"“{item['evidence']}”" if item["evidence"] else "—"] for item in items[:LIST_LIMIT]]
        blocks.append({"object": "block", "type": "table", "table": {
            "table_width": len(rows[0]),
            "has_column_header": True,
            "children": [{"object": "block", "type": "table_row", "table_row": {"cells": [rich_text(c) for c in row]}}
                         for row in rows],
        }})
        if len(items) > LIST_LIMIT:
            blocks.append(block("paragraph", f"...and {len(items) - LIST_LIMIT} more action items (see transcript)."))
    else:
        blocks.append(block("paragraph", "No action items."))

    if notes["assumptions"]:
        blocks.append(block("heading_2", "Assumptions made"))
        blocks += _bullets(notes["assumptions"], "")

    tokens = (f"{usage.get('promptTokenCount', 0)} in / {usage.get('candidatesTokenCount', 0)} out / "
              f"{usage.get('thoughtsTokenCount', 0)} thinking tokens")
    generated_on = (today or date.today()).isoformat()
    blocks += [
        {"object": "block", "type": "divider", "divider": {}},
        block("paragraph", f"Generated from {source} by {model} on {generated_on} ({tokens}). "
                           "Check against the transcript before relying on it."),
    ]
    return blocks
