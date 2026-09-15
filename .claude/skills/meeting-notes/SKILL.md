---
name: meeting-notes
description: Turn call transcripts (a .txt file, several files, a folder, or pasted text) into structured meeting-notes pages in the team's Notion database, using Gemini 3.8 Flash for extraction. Use when the user wants meeting notes, a call summary, decisions or action items written into Notion from a transcript.
argument-hint: <transcript file(s) or folder, or paste the transcript>
---

# /meeting-notes

Turns transcripts people already have (Zoom, Teams, Otter exports) into Notion pages with a summary, attendees, decisions and an action-items table. Action items whose owner isn't clearly named in the transcript are marked **please verify**.

**Gemini does the extraction, not you.** Your job is to get the transcript to the script, run it, and report what it did. Don't write, rewrite or "improve" the notes yourself. The point of this workflow is that Gemini 3.8 Flash produces them, and the script checks them.

## Steps

1. **Work out the input** from `$ARGUMENTS` and the conversation:
   - File paths or a folder → use them as given.
   - Transcript text pasted into the chat → save it with the Write tool to `transcripts/pasted-YYYYMMDD-HHMM.txt` (git-ignored) and use that path. Don't change the text.
   - Nothing → ask the user for a transcript file or pasted text, then stop.

2. **Run the script** from the project root:
   ```bash
   python .claude/skills/meeting-notes/meeting_notes.py <paths...>
   ```
   - Add `--dry-run` if the user wants a preview without writing to Notion.
   - Add `--force` only if the user explicitly wants a duplicate page for a transcript that was already imported.

3. **Report back** briefly, for each file:
   - `created`: the Notion page link, plus every action item marked **please verify** with its reason, word for word from the output. These are the ones a human needs to check.
   - `skipped`: the reason (empty, too short, garbled, not a meeting, already imported).
   - `failed`: the error and the fix below.

## Fixing failures

| Message | Tell the user |
|---|---|
| `Missing in .env: ...` | Copy `.env.example` to `.env` and fill in the named values. |
| `Notion rejected NOTION_TOKEN` | Copy the token again: Notion → Developer tools → Connections → Meeting Notes. |
| `Notion can't see the database` | Open the database → ••• → Connections → add the Meeting Notes connection, and check `NOTION_DATABASE_ID`. |
| `missing columns` | The database needs `Date` (date), `Attendees` (text), `Needs review` (checkbox), `Source` (text). |
| `Gemini: 429 ...` | Rate limit (common on the free tier). Wait a minute and re-run; already-imported files are skipped. |

Never print or read out the contents of `.env`.
