---
name: meeting-notes
description: Turn call transcripts (a .txt file, several files, a folder, or pasted text) into structured meeting-notes pages in the team's Notion database, using Gemini 3.8 Flash for extraction. Use when the user wants meeting notes, a call summary, decisions or action items written into Notion from a transcript.
argument-hint: <transcript file(s) or folder, or paste the transcript>
---

# /meeting-notes

Turns transcripts people already have (Zoom, Teams, Otter exports) into Notion pages with a summary, attendees, decisions and an action-items table. Action items whose owner isn't clearly backed by the transcript are marked **please verify**, and the page's `Needs review` box is ticked.

**Gemini does the extraction, not you.** Your job is to get the transcript to the script, run it, and report what it did. Don't write, rewrite or "improve" the notes yourself. The point of this workflow is that Gemini 3.8 Flash produces them and the code checks them.

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
   - Add `--force` only if the user explicitly wants a second page for a transcript that's already imported.
   - If the output says the Notion database isn't set up, run this once and then re-run the transcripts. It only adds missing columns and never changes existing ones:
     ```bash
     python .claude/skills/meeting-notes/meeting_notes.py --init-db
     ```

3. **Report back** briefly, for each file:
   - `created`: the Notion page link, plus every action item marked **please verify** with its reason, word for word from the output. These are the ones a human needs to check.
   - `skipped`: the reason (empty, too short, garbled, not a meeting, already imported).
   - `failed` or `not run`: the error and the fix below.

   Exit codes: `0` everything created, skipped or previewed · `1` at least one file failed · `2` setup problem.

## Fixing failures

| Output contains | Tell the user |
|---|---|
| `Missing in .env: ...` | Copy `.env.example` to `.env` and fill in the named values. |
| `Notion: the access token was rejected` | Copy the token again: Notion → Developer tools → Connections → Meeting Notes. |
| `Notion: the database isn't visible` | Open the database → ••• → Connections → add the connection, and check `NOTION_DATABASE_ID`. |
| `The Notion database isn't set up` | Run the `--init-db` command above, then re-run. |
| `Can't set up the database automatically` | A column has the wrong type. Rename or delete it in Notion, then run `--init-db`. |
| `Gemini: quota used up` | The API key's quota is exhausted. Wait, or enable billing on the Google Cloud project. |
| `Gemini busy (503)` then `not run` | Gemini is overloaded. Re-run later; transcripts already imported are skipped. |
| `Gemini: model ... isn't available` | Check `GEMINI_MODEL` in `.env`, or leave it blank for the default. |

Never print or read out the contents of `.env`.
