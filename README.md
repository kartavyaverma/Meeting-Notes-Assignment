# meeting-notes

A Claude Code skill, `/meeting-notes`, that turns a raw call transcript into a structured Notion page.

- **Extraction:** Gemini 3.8 Flash (`gemini-3.8-flash`) via the Gemini API: title, date, attendees, summary, decisions, action items.
- **Destination:** a Notion database, written through Notion's REST API.
- No hosted server, no frontend, no workflow builder. It runs from the terminal.

Action items with no clearly named owner are marked **please verify** so nobody is assigned a guessed owner.

## Setup

1. Copy `.env.example` to `.env` and fill in the three values.
2. Share your Notion meeting-notes database with your integration.

## Run

In Claude Code, from this folder:

```
/meeting-notes transcripts/sample-call.txt
```

The skill lives in `.claude/skills/meeting-notes/`. See `DOCUMENTATION.md` for the full write-up.
