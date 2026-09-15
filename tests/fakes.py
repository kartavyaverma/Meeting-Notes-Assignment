"""Test doubles and sample data shared across the test suite."""

import copy
import json

from meeting_notes.config import Settings

SETTINGS = Settings(
    gemini_api_key="test-gemini-key",
    notion_token="test-notion-token",
    notion_database_id="db123",
    input_usd_per_m=0.75,
    output_usd_per_m=3.75,
)


class FakeHttp:
    """Stands in for api.request_json: returns or raises scripted responses in order and records each call."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, method, url, headers, body=None):
        self.calls.append({"method": method, "url": url, "headers": dict(headers), "body": copy.deepcopy(body)})
        if not self.responses:
            raise AssertionError(f"unexpected request: {method} {url}")
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def meeting_notes(**overrides):
    """Normalized notes as the Gemini client returns them (before verification adds `verify`)."""
    notes = {
        "is_meeting_transcript": True,
        "rejection_reason": "",
        "title": "Kickoff",
        "date": "2026-09-10",
        "attendees": [{"name": "Daniel Okafor", "role": "Tech lead"}],
        "summary": "A kickoff.",
        "decisions": ["Split the project into two phases"],
        "action_items": [{
            "task": "Submit the Dentrix access request",
            "owner": "Daniel Okafor",
            "owner_status": "explicit",
            "evidence": "I'll submit the Dentrix developer access request by Friday",
            "due": "by Friday",
            "soft_commitment": False,
        }],
        "assumptions": [],
    }
    notes.update(overrides)
    return notes


def gemini_response(notes, usage=None, finish="STOP"):
    """A generateContent response wrapping `notes` as the model's JSON answer."""
    return {
        "candidates": [{"finishReason": finish, "content": {"parts": [{"text": json.dumps(notes)}]}}],
        "usageMetadata": usage or {"promptTokenCount": 1000, "candidatesTokenCount": 400, "thoughtsTokenCount": 0},
    }
