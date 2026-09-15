# Changelog

Notable changes to this project. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
- `PROJECT_STRUCTURE.md`: a file-by-file guide to the code, with flow and module diagrams.
- `main.py` at the project root as the single entry point: `python main.py transcripts/`.

### Changed
- Removed comments and docstrings from the code and configuration files. Their explanations now live in `PROJECT_STRUCTURE.md`.
- The tool is now a standalone command-line program; the previous launcher folder was removed.

## [1.0.0] - 2026-09-15

### Added
- `meeting-notes` command: transcript → Gemini 3.8 Flash extraction → formatted Notion page.
- Owner verification: each action item's evidence quote must exist in the transcript, be long enough to prove something, and come from or be addressed to the named owner. Anything else gets "please verify" reasons and ticks `Needs review`.
- Batch processing of files and folders. The batch stops early when Gemini is overloaded or out of quota instead of spending more requests.
- `--init-db` to add the required Notion columns. It never changes existing columns.
- Content-hash duplicate detection via a `Content hash` column, with a filename fallback for pages imported before hashes existed.
- `GEMINI_MODEL` setting, and a per-run cost when prices are configured.
- Offline test suite and a GitHub Actions workflow (Ubuntu and Windows, Python 3.9 and 3.13).
- `pyproject.toml`, `.editorconfig` and `.gitattributes`.

### Changed
- Split the single script into the `src/meeting_notes` package.
- The prompt now asks for evidence from a single speaker's line, after a live run showed quotes stitched across lines.
- Error messages name the service and the fix. Exit codes are documented: 0, 1, 2.

### Fixed
- Missing fields in a model response could share default lists between transcripts in the same batch.
- A page with very long lists could exceed Notion's 100-blocks-per-request limit.
- Transcripts in scripts that use combining marks, such as Devanagari, could be rejected as garbled.
- The duplicate check could confuse two different transcripts that share a filename.
