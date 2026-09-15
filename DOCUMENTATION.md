# AI Engineer Intern Assignment — Documentation

> **Status:** draft. Items marked `[PENDING …]` are filled in after the final recorded run and a pricing lookup. Items marked `[SCREENSHOT …]` / `[GIF …]` are what to capture.

---

## 1. The capability I spotted

**Capability:** Gemini 3.8 Flash (Google), released September 2, 2026, well within the assignment's "last few weeks" window. The build uses it directly as the model that reads a raw call transcript and pulls out structured meeting notes (attendees, decisions, action items).

**Why this counts as "new":** It has a specific, checkable release date (September 2, 2026). It isn't a general capability I already knew about. It's also the actual reasoning engine inside the workflow, not just the tool I used to write the code.

**Why this model instead of a flagship one:** This is a frequent, simple extraction task: every client call a business takes produces one. For a job that's structured extraction rather than deep multi-step reasoning, the cheapest model that still does it correctly is the right choice, because the cost repeats on every call.

What I measured (token counts come from Gemini's own `usageMetadata` on each response):

| Transcript | Length | Input tokens | Output tokens | Thinking tokens |
|---|---|---|---|---|
| BrightPath kickoff (4 people) | ~5 min, ~1,000 words | 2,324 | 1,094 | 0 |
| Ridgeline discovery (2 people) | ~2 min, ~400 words | 1,011 | 469 | 0 |

Real client calls run longer. At roughly 150 spoken words a minute, a 45-minute call is about 6,700 words, or around **9,000 input tokens and ~2,000 output tokens**. At the flagship headline price I noted for Claude Fable 5.1 and GPT-6 Astra ($10 input / $50 output per 1M tokens), that's about 9,000 × $10/1M + 2,000 × $50/1M ≈ **$0.19 per call**, which lines up with my original $0.15–0.20 estimate. For Gemini 3.8 Flash: [PENDING PRICE: work out 9,000 × input price + 2,000 × output price, and the multiple vs. $0.19]. One thing I only found by measuring: **thinking tokens**. A one-line test prompt used 98 hidden thinking tokens, billed as output. Setting `thinkingLevel: low` brought that to 0 on real transcripts without hurting accuracy, which matters more for cost than the headline price.

**The caveat I designed around:** Flash models give up some reasoning depth in exchange for speed and low cost. The real risk isn't total failure. It's **misattribution**: getting a decision or action item right but giving it to the wrong person, or missing a softer commitment ("I'll try to get that over" vs. an explicit "I will do X by Friday") that a stronger model might catch. So the build doesn't blindly trust every extracted action item. When the transcript doesn't explicitly name an owner, the output marks the item "please verify" instead of guessing.

**What testing actually showed:** across both transcripts (11 action items), **Gemini 3.8 Flash didn't misattribute a single owner**. That includes two traps I wrote on purpose: Mark is asked for the brand guidelines *through* Sarah and ends up owning them, and Daniel hands the sitemap to Aisha, so Priya owns "ask Aisha". It did flag every vague item correctly:

| Transcript line | What the page shows |
|---|---|
| "We'll get the revised quote over to you" | ⚠️ Please verify: owner inferred, not stated (best guess: Priya Nair) |
| "I'll try to get those over to you, but no promises this week" | ⚠️ Please verify: soft commitment, may not happen |
| "someone should probably loop in legal about the data side" | ⚠️ Please verify: no owner named in the transcript |

Its only mistakes were **omissions**: it didn't list "Daniel sends Sarah the forms to sign" or "set up the Tuesday check-in" as action items. Two transcripts is a small sample, so "no misattributions" means "none seen yet", not "never happens". That's exactly why the second safeguard doesn't depend on the model being right (see *How it works*, step 5).

**Where Notion fits in:** Notion is *not* the Part 1 capability. It's the existing tool the finished notes get written into, through a direct call to Notion's own REST API. That matches the "agent calling an existing tool's API" shape the assignment asks for.

---

## 2. The pain point I matched it to

**Pain point:** "Meeting notes never get written up, so decisions and follow-ups fall through." (from the assignment's own ICP pain list)

**Why this pairing makes sense:**
- A 50–300 person service/product business is on client and sales calls constantly. Nobody's job is taking notes, and writing them up afterward is the first thing people skip when they're busy.
- Most of these businesses already keep client and project records in Notion. Having structured notes just show up there removes a step instead of adding another tool to check.
- Extraction (attendees, decisions, action items) is a narrow, repeatable task. That suits a fast, cheap model better than a flagship one, and cost matters because this runs on *every* call a business takes, not once.
- No paid transcription or note-taker service is needed. This assumes the business already has a transcript (from Zoom, Otter's free tier, etc.) and starts from there.

**Doesn't Notion already do this with its built-in AI Meeting Notes?** Partly, yes. Since May 2025, Notion has had AI Meeting Notes: you type `/meet`, it records your system audio live, and it produces a transcript, summary and action items. I checked this before committing to the build. It leaves three real gaps that this workflow fills:
1. **It's built around live capture.** It has to be recording *during* the call, in the desktop app, on the machine where someone started it. It won't take a transcript that already exists in Zoom, Teams or a free Otter export and file it as structured notes. On a Business plan you *could* paste a transcript into Notion AI and ask for a summary, but that's a manual copy, prompt and reformat job each time, with no consistent structure and no owner checks. Existing transcripts are the more common case at a real business: calls happen in different tools on different people's machines, and nobody remembers to type `/meet` every time.
2. **Ongoing use is tied to Notion's paid AI plans.** I tested this myself: my workspace is on the **Free** plan and the `/meet` block still appeared with "Start transcribing", so Notion lets Free users *try* it. Continued use is part of Notion's Business plan (~$20–24/user/month, billed annually). [PENDING VERIFY on notion.com/pricing: the exact Free-plan trial limit for AI Meeting Notes.] Many businesses this size are on Free or Plus and won't pay for Business across the team just for notes. This workflow costs [PENDING PRICE] per meeting and needs no plan upgrade.
3. **It handles one meeting at a time, not a batch.** You can't point the built-in feature at a backlog of old transcripts and catch them all up at once. This workflow takes a whole folder in one command, and re-running the folder skips anything already imported.

So to be honest about it: Notion already solved this for Business-plan teams who record live in its desktop app. This build is for everyone else: teams on cheaper plans, or using whatever call tool they already have, who have a transcript and want it turned into structured Notion notes without copying, pasting and reformatting by hand.

---

## 3. The workflow — what / why / how

### What it does

You point `/meeting-notes` at a transcript file, several files, or a whole folder. For each one, Gemini 3.8 Flash pulls out the title, date, attendees, a short summary, decisions and action items, and a new page appears in the team's Notion `Meeting Notes` database. Every action item's owner is checked against the transcript's actual words. Anything not clearly owned is marked **⚠️ Please verify**, and the page's `Needs review` box is ticked, so it stands out in the database view.

`[SCREENSHOT: the Notion Meeting Notes database after the run, showing both rows with Name, Attendees, Date, Needs review ticked, and Source filled in]`

### Why this approach

**A skill plus a script, not a hosted app.** The assignment rules out servers and frontends, and this doesn't need one: transcripts already sit on someone's laptop or in a synced folder. The skill (`SKILL.md`) is the entry point in Claude Code, and the actual work is one Python file using only the standard library, so there's nothing to install and nothing to deploy. The script also runs on its own from any terminal, which is what you'd put on a schedule later.

**Gemini does the extraction, not Claude.** The Claude Code skill only finds the transcript, runs the script and reports back. `SKILL.md` explicitly tells Claude not to write or "improve" the notes. If Claude summarized the transcript itself, the Part 1 capability wouldn't be doing the work, and every run would pay agent-model prices instead of Flash prices.

**Notion's REST API, not the Notion MCP server.** With MCP, an agent model decides what to send to Notion on every run, so the page layout can vary from run to run, and each write goes through another model call. With the REST API, the script builds the exact same page structure every time (callout, headings, bullets, a 5-column table), and I could test it with made-up data without spending any Gemini quota. The MCP server also wasn't new enough to count as the Part 1 capability. **What it cost me:** about 60 lines of block-building code, and handling Notion's API details myself (rich-text length limits, a table's rows having to be created together with the table).

**A fixed JSON schema, not free text.** Gemini is called with `responseMimeType: application/json` and a `responseSchema`, so it can only return the fields the page needs. The formatting can't break because the model decided to answer in prose.

**Check owners in code, not by trusting the model.** Gemini labels each owner `explicit`, `implied` or `unassigned`, but a model's confidence in its own answer is exactly what you can't trust from a model tuned for speed. So the script independently checks each owner against the transcript (step 5 below).

**Tradeoffs I accepted:**
- **It runs when someone invokes it**, not automatically after every call (see interview question 6 for how I'd automate it).
- **It needs an existing transcript.** It doesn't record or transcribe audio.
- **It's built on a days-old model.** During testing the free tier returned `503 high demand` repeatedly and ran out of quota at 20 requests. See the build log and interview question 9.

### How it works (step by step)

1. **A transcript lands in `transcripts/`.** It can be a Zoom/Teams export (`[00:01:02] Name: text`) or an Otter export (a `Name  0:12` line, then the text). If someone pastes a transcript into Claude Code instead, the skill saves it to `transcripts/pasted-<timestamp>.txt` first. Only files named `sample-*` are committed to git; everything else in that folder stays local, because real transcripts contain client data.

2. **`/meeting-notes transcripts/` runs the script.**
   ```bash
   python .claude/skills/meeting-notes/meeting_notes.py transcripts/
   ```
   It loads keys from `.env`, then makes **one Notion call up front** to confirm the database exists, the connection can see it and all the columns are there. A broken setup fails right away, before any Gemini tokens are spent.

3. **Cheap checks come before any API call.** Empty files, files with fewer than 40 words, and files that are mostly symbols get skipped locally. A transcript whose filename is already in the database's `Source` column is skipped too, so re-running a folder never creates duplicates.

4. **Gemini 3.8 Flash extracts the notes.** The call carries a system prompt with the rules (only use what's in the transcript; follow hand-offs to the person who actually ends up responsible; mark "someone should…" as unassigned; copy the evidence word for word), the JSON schema, and `thinkingLevel: low`. For each action item it returns `task`, `owner`, `owner_status`, `evidence` (the exact quote), `due` and `soft_commitment`. It can also answer `is_meeting_transcript: false`: a recipe I fed it came back as *"a baking recipe and not a conversation or meeting transcript"* and was skipped.

5. **The script checks every owner against the transcript.** It splits the transcript into who-said-what, handling both the Zoom and Otter formats. An action item is marked **⚠️ Please verify** if any of these is true:
   - no owner is named, or the owner is only inferred
   - the quoted evidence doesn't appear word for word in the transcript (a hallucinated quote)
   - the quote exists, but it wasn't said by, or to, the named owner (a misattribution)
   - it's a hedged promise ("I'll try, no promises")

   Gemini made no misattributions in testing, so I tested this check by feeding it deliberately wrong owners and an invented quote (`python tests/test_checks.py`, no API calls needed). It caught all 4 bad items and passed all 3 correct ones, in both transcript formats.

   `[SCREENSHOT: terminal output of python tests/test_checks.py, showing every PASS line and "All checks passed."]`

6. **The Notion page is created** with one `POST /v1/pages` call:
   - **Properties:** `Name`, `Date` (only if the transcript states it; otherwise left blank and listed as an assumption), `Attendees`, `Needs review`, `Source`
   - **Body:** a ⚠️ callout ("2 of 8 action items need a human check…"), Summary, Attendees, Decisions, an **Action items table** (Task · Owner · Due · Status · From the transcript), the assumptions Gemini made, and a footer with the model name and token counts

   `[SCREENSHOT: the top of the BrightPath Notion page: the yellow callout, Summary, Attendees and Decisions]`
   `[SCREENSHOT: the BrightPath action-items table, with the ✅ rows and the ⚠️ Please verify rows (revised quote, analytics logins, legal) visible]`

7. **A batch summary prints at the end.** If Gemini is overloaded or out of quota, the batch stops after 2 spaced retries and marks the remaining files "not run", instead of burning quota on each one. Running it again later picks up where it stopped.

   `[SCREENSHOT: the terminal after the run, showing the extracted notes for both files, the ⚠️ please-verify lines, the "created" links and the "Done: 2 file(s)" summary]`

`[GIF: one continuous clip with the terminal and Notion side by side: typing python .claude/skills/meeting-notes/meeting_notes.py transcripts/, the notes printing for each file, both rows appearing in the Notion database, then opening the BrightPath page and scrolling to the ⚠️ Please verify rows]`

[PENDING RUN: note that the GIF shows the script the skill calls, run straight from the terminal; the skill is a thin wrapper, so the run is identical.]

**Setup screenshots:**
`[SCREENSHOT: Google AI Studio showing the Gemini API key created (key value blurred)]`
`[SCREENSHOT: the terminal showing the successful test call to gemini-3.8-flash: "meeting-notes test OK" and the usage line with 98 thinking tokens]`
`[SCREENSHOT: the Notion connection settings page (Developer tools → Connections → Meeting Notes) showing Access token auth, only Read/Update/Insert content enabled, and the token hidden as dots]`
`[SCREENSHOT: the "Add Meeting Notes to this page" dialog listing the connection's capabilities: can read/insert/update content, cannot comment]`
`[SCREENSHOT: the empty Meeting Notes database before the first run, showing the Name, Attendees, Date, Needs review and Source columns]`
`[SCREENSHOT (optional): /meeting-notes showing in the command suggestions of a Claude Code session started in the project folder]`

### Edge cases I actually hit

| What happened | How it's handled |
|---|---|
| Empty, too-short or garbled file | Skipped locally with the reason; no API call |
| Text that isn't a meeting (a recipe) | Gemini returns `is_meeting_transcript: false`; skipped, nothing written |
| No date in the transcript (Ridgeline) | `Date` left blank; "No meeting date was stated" added under assumptions, never guessed |
| Wrong database ID, or database not shared | Fails before any Gemini call: "Notion can't see the database. Check NOTION_DATABASE_ID…" |
| Invalid Notion token | Fails before any Gemini call: "Notion rejected NOTION_TOKEN…" |
| `503 high demand` from Gemini (repeatedly) | 2 retries, 20s and 40s apart, with a visible message; then the batch stops and marks the remaining files "not run" |

`[SCREENSHOT: the terminal with both overloaded runs, one above the other: the first (old code) failing both files with no retries shown, and the second (new code) showing "Gemini busy (503), retrying in 20s (1/2)", "retrying in 40s (2/2)", then Ridgeline marked "not run"]`
| `429` free-tier quota used up (20 requests) | Stops immediately, since retrying can't help |
| Re-running a folder | Files already in the database are skipped via `Source`; `--force` re-imports |
| A file that can't be read (hit a Windows 260-character path limit) | That file is marked failed; the rest of the batch continues |

---

## 4. Other capability-to-pain-point pairings I considered

*(based on research into what shipped recently, as of mid-September 2026)*

| Capability | Type | Pain point it could solve | Why I didn't build this one |
|---|---|---|---|
| Official Notion MCP server | New connector | Meeting notes / onboarding / dashboards: anything that writes into Notion | I checked its release date and it isn't actually new. It first shipped in April 2025, with a "3.5" feature update in May 2026, so it misses the assignment's "last few weeks" bar for Part 1. Notion stays in the build only as the destination tool, called through its plain REST API, not as the Part 1 capability |
| Notion's built-in AI Meeting Notes (`/meet`) | Existing built-in feature, not something to build | The same pain point: meeting notes never get written up | Not a "capability I spotted", since it already exists and isn't new. I'm naming it because it's the obvious "why build this yourself?" question. It captures live, in the desktop app, and needs Notion's Business plan for ongoing use. My build covers existing transcripts and cheaper plans, so I treated it as the competitor to set this apart from, not a pairing to build |
| Claude Fable 5.1 (Anthropic, Sept 1, 2026) | New model | The same task, with stronger reasoning | Same headline price as GPT-6 Astra ($10/$50 per million tokens), about $0.19 for a 45-minute call by my token estimate, for a task that's structured extraction, not deep reasoning. Ruled out on cost per run for a workflow meant to run on every call |
| GPT-6 Astra (OpenAI, Sept 3, 2026) | New model | Drafting personalized replies to leads from form submissions | More reasoning power than this task needs, the same cost problem as Fable 5.1 above, and it would add a second provider and API key to the workflow |
| Slack native MCP support | New connector | A DM or comment sits unanswered for hours | Real ICP pain, but testing the native MCP path needs a live Slack workspace on Business+ or Enterprise, which is hard to demo end to end in 1–3 days on a personal account |
| Meta Muse Spark 1.3 (Sept 2, 2026) | New agent model | [PENDING: the pain point you considered it for, or remove this row] | Less documentation on what actually changed in 1.3 vs 1.2, so more research risk for a 1–3 day build |
| Salesforce Agentforce named agents (Sept 11, 2026) | New agent product | Several ICP pains at once (sales, service, support) | It's a full platform, not something I can wire together myself in a small script, which goes against the assignment's "not a hosted application" rule |

---

## 5. Likely interview questions

1. **Doesn't Notion already do this natively with its AI Meeting Notes feature?**
   Partly, and I checked before building. Notion's `/meet` records a call live in the desktop app and writes a summary with action items. It does that well if you're on the Business plan and remember to start it before the call. My workspace is on Free and I could see the feature, but ongoing use needs Business. What it doesn't do is take the transcripts a business *already has* (Zoom, Teams, Otter), process a backlog of them in one go, or check who actually owns each task. My build covers exactly that gap, for teams that won't upgrade everyone to Business just for notes.

2. **Why did you pick a Flash-tier model instead of a flagship one?**
   Because this runs on every call, and the task is extraction, not reasoning. From real token counts, a 45-minute call is about 9,000 tokens in and 2,000 out. That's roughly $0.19 at flagship prices and [PENDING PRICE] on Gemini 3.8 Flash. Accuracy held up on my test transcripts: every owner was correct, including two deliberate traps. The one real weakness I saw was omissions, not wrong answers. And I didn't rely on the cheaper model being right: owners are checked in code afterwards.

3. **What happens if the transcript is garbled or the call was cut short — does the skill fail gracefully?**
   Yes, and I tested each case. Empty, too-short (under 40 words) and mostly-symbol files are skipped locally before any API call. Text that isn't a meeting gets rejected by Gemini itself: I fed it a recipe and it came back `is_meeting_transcript: false`, with nothing written. A cut-short call that's still a real conversation gets processed, with whatever decisions and items it actually contains. Anything missing, like the date, is left blank and listed under "Assumptions made" rather than invented. In a batch, one bad file never stops the others.

4. **Why call Notion's REST API directly instead of using the Notion MCP server?**
   Predictability and cost. With MCP, a model decides what to write on every run, so the page structure can drift, and every write goes through another model call. With the REST API, the page is built by code: the same callout, headings and 5-column table every time. I could also test it with made-up data at zero Gemini cost. The MCP server also wasn't new enough to count as the Part 1 capability. The price was about 60 lines of block-building code.

5. **Why a Claude Code skill instead of a scheduled/cron job?**
   For a first version, a person looking at the output is a feature: the ⚠️ items need someone to check them anyway, and the skill fits into how the team already works in Claude Code. It also handles the "I'll just paste this transcript" case. But the logic lives in a plain script that runs fine without Claude, so a scheduled job is one step away, not a rewrite (next question).

6. **How would you turn this into something that runs automatically after every call, without you manually invoking it?**
   Most call tools can save transcripts to a synced folder (Zoom cloud recording exports, or a shared Google Drive or OneDrive folder). I'd schedule the existing script against that folder every 15 minutes, with Windows Task Scheduler or cron. Because it already skips files it has imported, re-running the whole folder is safe, and because it stops cleanly on overload, the next run picks up anything that failed. The fully push-based version, where Zoom notifies you the moment a transcript is ready, needs a small hosted endpoint. That's outside this assignment's rules, but it would be the production step.

7. **What's the actual caveat you designed around, and how does the safeguard work end to end?**
   Misattribution: Flash-tier models can get a task right but pin it on the wrong person. There are two layers. First, Gemini has to label each owner `explicit`, `implied` or `unassigned`, and copy the exact words where the commitment was made. Second, the script doesn't trust that label. It checks that the quote really appears in the transcript, and that it was said by or to the named owner, using the speaker labels. Anything that fails, or is implied, unassigned or hedged, becomes "⚠️ Please verify: <reason>" in the action-items table and ticks `Needs review` on the database row. I tested the second layer with deliberately wrong owners and a fake quote: 4 of 4 caught, 3 of 3 correct ones passed.

8. **Why this pain point specifically, out of the six the assignment listed?**
   It happens on every client call, so it's constant, not occasional. The cost of missing it is concrete: a forgotten follow-up is a lost deal or an unhappy client. And it maps cleanly onto what a cheap, fast model does well. It also has a clear "before and after" you can verify: either the action items with owners are in Notion, or they aren't.

9. **What would break first if 50 people at a company used this simultaneously?**
   **Gemini capacity and quota come first, and I hit both in testing with just one user:** repeated `503 high demand`, and the free tier's 20-request limit. At team scale you'd need a billed project, a queue that spreads requests out, and a fallback model for demand spikes. **Next is Notion's rate limit,** since everyone shares one connection token (each file makes about 3 Notion calls). **Then duplicate detection, which is filename-based:** two people importing different transcripts both called `call.txt` would collide, so I'd switch to a hash of the file contents. **There's also a governance issue:** one token on everyone's laptop in `.env` is fine for a prototype but not for 50 people.

10. **Why didn't you use a visual/no-code tool — wasn't that faster?**
    It's not allowed by the assignment, and it wouldn't have been faster for the parts that matter. The owner check is ~30 lines of logic that splits a transcript by speaker and matches quotes. That's awkward to build out of visual nodes and hard to test. In code I can run `python tests/test_checks.py` in a second, see exactly what failed, and version it in git.

11. **How did you validate the output was actually correct and not hallucinated action items?**
    Three ways. **First,** I wrote the test transcripts myself with known answers, including traps (a hand-off, a task redirected to someone else, a hedged promise, an unowned "someone should"), then compared Gemini's output line by line: all 11 owners were correct, and there were 2 omissions and no invented items. **Second,** every action item carries a word-for-word quote, and the script checks that quote exists in the transcript, which is a direct test for hallucination. **Third,** I tested that check itself with deliberately wrong data. The honest limit: two transcripts is a small sample. With another week, I'd build a labelled set of 20–30 real (anonymized) transcripts and measure owner accuracy properly.

12. **What would this actually cost a business running it at real volume — say 20 calls a week?**
    [PENDING PRICE: 20 × (9,000 input + 2,000 output tokens) = 180,000 input + 40,000 output tokens a week. Multiply by Gemini 3.8 Flash prices for a weekly and monthly figure (×4.3), and compare with ~$16/month at flagship prices (20 × $0.19 × 4.3).] Notion's API is free on any plan, and there's no hosting cost because nothing is hosted.

13. **If you had another week, what's the next thing you'd build on top of this?**
    - **An evaluation set:** 20–30 anonymized real transcripts with hand-labelled owners, to measure how often Flash gets owners wrong vs. a flagship model, and decide with data instead of a hunch.
    - **Close the loop on ⚠️ items:** post each "please verify" item to the relevant person in Slack, and link owners to actual Notion users, so tasks show up on the right person's plate.
    - **The scheduled folder watcher** from question 6, with content-hash deduplication.

---

## 6. Appendix — raw research notes

Capabilities that shipped in the ~2 weeks before this build (for reference and as an audit trail):
- Sept 1, 2026: Claude Fable 5.1 and Mythos 5.1 (Anthropic)
- Sept 2, 2026: Gemini 3.8 Flash + gated Cyber variant (Google); Muse Spark 1.3 (Meta)
- Sept 3, 2026: GPT-6 Astra (OpenAI)
- Sept 10, 2026: DeepSeek V4.1 Flash
- Sept 11, 2026: Fugu Ultra v2.0 and Fugu Max (Sakana AI); Salesforce Agentforce named agents
- Ongoing: Slack native MCP support (Business+/Enterprise); official Notion MCP server; Hex as an MCP client

Sources checked: LLM Gateway release timeline, Capital & Compute model tracker, Agentic.ai news, AI Agent Store weekly digest, and the per-token pricing pages for Gemini 3.8 Flash, Claude Fable 5.1, and GPT-6 Astra (used to compare cost per run before picking Gemini 3.8 Flash). Also Notion's official MCP server changelog and GitHub repo, which confirmed it was *not* recent enough for Part 1 (first shipped April 2025, "3.5" update May 2026), and Notion's AI Meeting Notes help page and pricing page (live capture in the desktop app, Business plan).

---

## 7. Build log

- **Step 1: Scaffold.** Created the project folder with README, `.env.example`, `.gitignore` (ignores `.env` and every transcript except `sample-*`), a `/transcripts` folder, and this document. Chose plain Python with only the standard library (`urllib`) so there's nothing to install and the whole flow is two HTTP calls you can read.
- **Step 2: API access.** Created a Notion connection (Developer tools → Connections → New connection) using **Access token** auth, scoped to one workspace, with only Read/Update/Insert content and **no user information**, so it gets the least access it needs. Notion had renamed "integrations" to "connections" since most tutorials were written, so `.env.example` points to the new location. Created an empty full-page `Meeting Notes` database (deliberately *not* Notion's "Meeting Notes" template, which sets up Notion's own AI Meeting Notes) and shared only that database with the connection. Then, through the API, found the database ID and added the columns the skill writes: `Date` (date, so notes sort and filter by meeting date), `Attendees` (text), `Needs review` (checkbox, ticked when any action item has an unconfirmed owner, so the misattribution safeguard is visible from the database view without opening each page), and `Source` (the transcript filename, so a batch run can be traced back to its file). Notion test call: created a throwaway page `API connection test (safe to delete)` in the database. Gemini test call: created a free-tier API key in Google AI Studio and sent a trivial prompt to `gemini-3.8-flash`, which answered correctly. Usage came back as 9 prompt tokens, 4 output tokens **and 98 "thinking" tokens**: even a one-line reply triggered hidden reasoning, and thinking tokens are billed as output. That matters for cost at volume, so the extraction call sets a low thinking level. Pulling structure out of a transcript doesn't need much reasoning, and the owner-verification flag covers the one place where weaker reasoning could hurt. Testing was done on the **free tier** with fictional transcripts, because free-tier inputs may be used by Google to improve its products. Real client transcripts need a billed project.
- **Step 3: Build and first tests.** Built the skill as `SKILL.md` plus one standard-library Python script. Dry runs on both fictional transcripts got every action-item owner right, including a deliberate trap (Mark is asked about the brand guidelines via Sarah and ends up owning them) and a hand-off (Daniel passes the sitemap to Aisha, and Priya ends up owning "ask Aisha"). Every vague item was flagged: "we'll get the quote over" (implied owner), "I'll try, no promises" (soft commitment), "someone should loop in legal" (unassigned). Gemini made no misattributions, so I tested the code-level owner check separately by feeding it deliberately wrong owners and an invented quote: it caught all 4 bad items, passed all 3 correct ones, and worked on both Zoom-style and Otter-style transcripts. Those checks now live in `tests/test_checks.py` and run offline. Two small misses from Gemini: it didn't list "Daniel sends Sarah the forms to sign" or "set up the Tuesday check-in" as action items. Those are omissions, not misattributions. With `thinkingLevel: low`, thinking tokens dropped from 98 on the test call to 0 on real transcripts. Local checks skipped empty, too-short and garbled files before any API call, and a wrong database ID or bad Notion token failed before any Gemini tokens were spent. Before the recorded run, I checked the Notion page format with made-up notes (no Gemini call): every block type was accepted, the duplicate check found the page, and the test page was moved to trash.
- **The free tier fell over during testing, which is a real finding.** A new model on the free tier is fragile. I hit repeated `503 high demand` errors, then `429 quota exceeded` at **20 free-tier requests** for `gemini-3.8-flash`. Automatic retries on the 503s used up that quota faster, so the script now stops immediately on a quota error instead of retrying. The first recorded batch run failed the same way: both transcripts got `503 high demand`, and the old retry loop (5 tries per file) spent about 10 of the 20 free requests without producing anything. I changed three things: (1) only 2 retries, 20s and 40s apart, since failed calls can still count against quota; (2) the script prints "Gemini busy, retrying in 20s" so a wait doesn't look like a hang; (3) a batch stops at the first overload or quota failure and marks the remaining files "not run" instead of burning requests on each one. Re-running is safe because pages already created are skipped. In a simulated overload, a 2-file batch now uses 3 requests instead of 10. The next real attempt hit the same overload and behaved exactly that way: two visible retries, then it stopped, using 3 requests. **Lesson for production:** a days-old model has capacity risk. You'd run on a billed project, queue failed transcripts to retry later, and consider a fallback model for demand spikes.
- **Step 4: Recorded run.** [PENDING RUN: the exact terminal output, what was written to Notion (read back through the API), and anything unexpected.]
