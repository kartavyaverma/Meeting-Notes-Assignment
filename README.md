# meeting-notes

A Claude Code skill, `/meeting-notes`, that turns call transcripts you already have into structured Notion pages.

- **Extraction:** Gemini 3.8 Flash (`gemini-3.8-flash`) via the Gemini API: title, date, attendees, summary, decisions, action items.
- **Safeguard:** each action item's owner has to be backed by a word-for-word quote from, or naming, that person. Anything else is marked **please verify**, and the page's `Needs review` box is ticked.
- **Destination:** a Notion database, written through Notion's REST API.
- No hosted server, no frontend, no workflow builder, no dependencies beyond Python 3.8+.

## Setup

1. Copy `.env.example` to `.env` and fill in the three values.
2. Create a Notion database with columns `Date` (date), `Attendees` (text), `Needs review` (checkbox), `Source` (text), and add your connection to it (••• → Connections).

## Run

In Claude Code, from this folder:

```
/meeting-notes transcripts/sample-client-kickoff-brightpath.txt
/meeting-notes transcripts/
```

Or run the script directly:

```bash
python .claude/skills/meeting-notes/meeting_notes.py transcripts/ --dry-run
```

`--dry-run` prints the extracted notes without writing to Notion. Re-running a folder skips transcripts already imported; use `--force` to import them again.

See `DOCUMENTATION.md` for the full write-up.
