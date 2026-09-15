# meeting-notes

A Claude Code skill (`/meeting-notes`) and command-line tool that turns call transcripts you already have into structured pages in a Notion database.

- **Extraction:** Gemini 3.8 Flash reads the transcript and returns the title, date, attendees, a summary, decisions and action items.
- **Safeguard:** every action item's owner has to be backed by a word-for-word quote from, or addressed to, that person. Anything else is marked **⚠️ Please verify** with the reason, and the page's `Needs review` box is ticked.
- **Destination:** a Notion database, written through Notion's REST API.
- **Footprint:** Python standard library only. No server, no frontend, nothing to deploy.

For a file-by-file explanation of the code, see [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md). For the design reasoning, test results and assignment write-up, see [DOCUMENTATION.md](DOCUMENTATION.md).

---

## Requirements

- Python 3.9 or newer
- A **Gemini API key** from Google AI Studio. Use a project with billing enabled: the free tier is heavily throttled for this model, and free-tier inputs may be used by Google to improve its products.
- A **Notion connection** (access token) with Read, Update and Insert content, added to one database

## Setup

1. **Keys.** Copy the example file and fill in the values:
   ```bash
   copy .env.example .env
   ```
2. **Notion.**
   1. In Notion, go to **Developer tools → Connections → New connection**, choose **Access token**, and enable Read/Update/Insert content (no user information needed). Copy the token into `NOTION_TOKEN`.
   2. Create an empty full-page database, open **••• → Connections**, and add your connection.
   3. Copy the database ID (the 32-character code before `?v=` in its URL) into `NOTION_DATABASE_ID`.
3. **Columns.** Add the columns the tool writes. This is safe to run again; it only adds what's missing:
   ```bash
   python .claude/skills/meeting-notes/meeting_notes.py --init-db
   ```

## Usage

**In Claude Code**, from this folder:

```
/meeting-notes transcripts/
/meeting-notes transcripts/sample-client-kickoff-brightpath.txt
```

You can also paste a transcript into the chat and ask for meeting notes.

**From a terminal:**

```bash
python .claude/skills/meeting-notes/meeting_notes.py transcripts/
python .claude/skills/meeting-notes/meeting_notes.py transcripts/ --dry-run
```

Or install it once (`pip install -e .`) and use the `meeting-notes` command instead.

| Option | Effect |
|---|---|
| `paths...` | Transcript `.txt` files, or folders of them |
| `--dry-run` | Extract and print the notes without writing to Notion (no Notion keys needed) |
| `--force` | Create a page even if the transcript was already imported |
| `--init-db` | Add any missing columns to the Notion database, then exit |
| `--version` | Print the version |

| Exit code | Meaning |
|---|---|
| `0` | Every file was created, skipped or previewed |
| `1` | At least one file failed |
| `2` | Setup problem: missing keys, bad paths, or an unreachable or incomplete Notion database |

Transcripts can be Zoom/Teams style (`[00:01:02] Name: text`) or Otter style (a `Name  0:12` line followed by the text), in UTF-8, UTF-16 or Windows-1252.

## Configuration

All settings come from environment variables, usually through `.env`. Real environment variables take precedence over the file.

| Variable | Required | Purpose |
|---|---|---|
| `GEMINI_API_KEY` | Yes | Google AI Studio API key |
| `NOTION_TOKEN` | Yes, except with `--dry-run` | Notion connection access token |
| `NOTION_DATABASE_ID` | Yes, except with `--dry-run` | Target database (dashes optional) |
| `GEMINI_MODEL` | No | Model to call; defaults to `gemini-3.8-flash` |
| `GEMINI_INPUT_USD_PER_M` / `GEMINI_OUTPUT_USD_PER_M` | No | Prices per 1M tokens; when set, each run prints its cost |

## Notion database columns

| Column | Type | Written as |
|---|---|---|
| *(title)* | Title | Meeting title |
| `Date` | Date | Meeting date, only if the transcript states it |
| `Attendees` | Text | Comma-separated names |
| `Needs review` | Checkbox | Ticked when any action item needs a human check |
| `Source` | Text | Transcript filename |
| `Content hash` | Text | SHA-256 of the transcript, used to skip duplicates |

## How it works

1. Settings load and the Notion database is checked once, before any tokens are spent.
2. Each transcript is read and prechecked locally: empty, too-short and garbled files are skipped.
3. Transcripts already in Notion (same content hash, or the same filename for pages imported before hashes existed) are skipped.
4. Gemini 3.8 Flash extracts the notes as JSON against a fixed schema, with a low thinking level.
5. Each owner is verified against the transcript; dates that aren't stated are left blank.
6. A formatted page is created: review callout, summary, attendees, decisions, action-items table, assumptions and a footer with the model and token counts.
7. If Gemini is overloaded or out of quota, the batch stops after two spaced retries and marks the remaining files "not run"; re-running picks up where it stopped.

## Project structure

```
.claude/skills/meeting-notes/
  SKILL.md              Skill instructions for Claude Code
  meeting_notes.py      Entry point; puts src/ on the path and runs the CLI
src/meeting_notes/
  cli.py                Arguments, batch runner, output and exit codes
  config.py             .env loading and settings validation
  api.py                JSON-over-HTTPS helper and ApiError
  gemini.py             Prompt, response schema, retries, parsing, cost
  transcript.py         Reading, prechecks, speaker splitting, content hash
  verification.py       Owner verification and date handling
  notion.py             Database checks and setup, duplicates, page building
tests/                  Offline test suite (no network, no keys)
transcripts/            Input; only sample-* files are committed
.github/workflows/      CI: runs the tests on Ubuntu and Windows
DOCUMENTATION.md        Assignment write-up and build log
PROJECT_STRUCTURE.md    File-by-file guide to the code
CHANGELOG.md            Release notes
```

## Development

Run the test suite from the project root. It makes no network calls and needs no keys:

```bash
python -m unittest -v
```

Conventions:
- Standard library only, so the skill runs anywhere Python does.
- API clients take injectable `http`, `sleep` and `notify` functions, so every behaviour, including retries and failures, can be tested without calling Gemini or Notion.
- User-facing errors say what to do next. Setup problems exit with code 2.

CI runs the same suite on Ubuntu and Windows with Python 3.9 and 3.13 on every push and pull request.

## Security and privacy

- `.env` is git-ignored. Never commit keys; if one is ever exposed (in a screenshot, recording or chat), rotate it.
- Everything in `transcripts/` is git-ignored except `sample-*` files, because real transcripts contain client data.
- The Notion connection only sees databases you add it to and doesn't need user information.
- Set a budget alert on the Google Cloud billing account.

## Limitations

- The model's own labels vary between runs on the same transcript. The ⚠️ flags are the safeguard; a person still reviews flagged items.
- Speaker detection expects Latin-script speaker names. With other scripts the owner check can't tie quotes to speakers, so it errs toward flagging.
- Each page lists at most 25 items per section, with a note when there are more.
- Editing a transcript changes its content hash, so an edited file is imported as a new page.
- It needs an existing transcript. It doesn't record or transcribe audio.
