# AI Engineer Intern Assignment — Documentation

> **Status:** complete, apart from the images themselves. Every `[SCREENSHOT …]` and `[GIF …]` marker describes exactly what to capture and paste in at that spot. Usage and setup instructions live in [README.md](README.md).

---

## 1. The capability I spotted

**Capability:** Gemini 3.8 Flash (Google), released September 2, 2026, well within the assignment's "last few weeks" window. The build uses it directly as the model that reads a raw call transcript and pulls out structured meeting notes (attendees, decisions, action items).

**Why this counts as "new":** It has a specific, checkable release date (September 2, 2026). It isn't a general capability I already knew about. It's also the actual reasoning engine inside the workflow, not just the tool I used to write the code.

**Why this model instead of a flagship one:** This is a frequent, simple extraction task: every client call a business takes produces one. For a job that's structured extraction rather than deep multi-step reasoning, the cheapest model that still does it correctly is the right choice, because the cost repeats on every call.

What I measured (token counts come from Gemini's own `usageMetadata`; cost uses Google's paid-tier rates of **$0.75 per 1M input tokens and $3.75 per 1M output tokens**, thinking included, valid through December 31, 2026):

| Transcript | Length | Input tokens | Output tokens | Thinking tokens | Cost per run |
|---|---|---|---|---|---|
| BrightPath kickoff (4 people) | ~5 min, ~1,000 words | 2,324–2,343 | 1,064–1,164 | 0 | $0.0057–0.0061 |
| Ridgeline discovery (2 people) | ~2 min, ~400 words | 1,011–1,030 | 381–467 | 0 | $0.0022–0.0025 |

*(Ranges cover three runs; see "Same transcript, three runs" below.)*

Real client calls run longer. At roughly 150 spoken words a minute, a 45-minute call is about 6,700 words, or around **9,000 input tokens and ~2,000 output tokens**:

| Model | Price per 1M tokens (in / out) | 45-minute call |
|---|---|---|
| Flagship (Claude Fable 5.1, GPT-6 Astra) | $10 / $50 | 9,000 × $10/1M + 2,000 × $50/1M ≈ **$0.19** |
| Gemini 3.8 Flash (2026 rates) | $0.75 / $3.75 | 9,000 × $0.75/1M + 2,000 × $3.75/1M ≈ **$0.014** |
| Gemini 3.8 Flash (from Jan 1, 2027) | $1.50 / $7.50 | ≈ **$0.029** |

So Flash is **about 13x cheaper** per call today, and still about 7x cheaper after Google doubles its prices in 2027. That's a little less than the 15–25x I estimated before building; the measured number is the one I'd stand behind. One thing I only found by measuring: **thinking tokens**. A one-line test prompt used 98 hidden thinking tokens, which are billed at the output price. Setting `thinkingLevel: low` brought that to 0 on real transcripts without hurting accuracy, so output cost stays predictable instead of depending on how long the model decides to think.

**The caveat I designed around:** Flash models give up some reasoning depth in exchange for speed and low cost. The real risk isn't total failure. It's **misattribution**: getting a decision or action item right but giving it to the wrong person, or missing a softer commitment ("I'll try to get that over" vs. an explicit "I will do X by Friday") that a stronger model might catch. So the build doesn't blindly trust every extracted action item. When the transcript doesn't clearly back an owner, the output marks the item "please verify" instead of guessing.

### Same transcript, three runs

I ran both transcripts through Gemini 3.8 Flash three times: the first real run, the recorded run, and a dry run after the production refactor. The model's answers were **not stable**, and that turned out to be the most useful thing testing showed:

| | Run 1 (first real run) | Run 2 (recorded run) | Run 3 (dry run, after refactor) |
|---|---|---|---|
| BrightPath decisions | 5 | 4 | 4 |
| BrightPath action items / flagged | 8 / 4 | 8 / 3 | 8 / 3 |
| Dentrix sign-off step | "Daniel sends Sarah the forms" (⚠️ inferred, quote stitched from two lines) | "Sarah signs the paperwork" (✅ explicit) | "Sarah signs the paperwork" (✅ explicit) |
| Revised-quote owner (Priya) | ⚠️ inferred; quote not found | ⚠️ inferred | ⚠️ inferred; quote too short ("Will do.") |
| Ridgeline "check with finance" | ⚠️ Tom, inferred | ⚠️ Unassigned | **left out entirely** |
| Owners assigned to the wrong person | **0** | **0** | **0** |

Across all three runs and every action item, **Gemini never assigned a task to the wrong person**, including two traps I wrote on purpose: Mark is asked for the brand guidelines *through* Sarah and ends up owning them, and Daniel hands the sitemap to Aisha, so Priya owns "ask Aisha". What *did* change from run to run was how confident it was and what it chose to include. That's exactly why the flag comes from code rather than from the model: the model's own `owner_status` label moved around, but every genuinely ambiguous item was flagged in every run. Some flags are the check being **deliberately cautious**: when Gemini paraphrased a correct owner's words, stitched two lines together, or offered a two-word quote, the item was flagged anyway. A false alarm costs someone a quick look; a wrong owner stated with confidence is the failure I actually care about.

The honest limit: the safeguard checks the items Gemini returns, so it **can't catch an item Gemini leaves out**. In run 3, "check with finance" simply wasn't there. That's the next thing I'd work on (interview question 10).

Examples of what the flags look like on the page:

| What Gemini extracted it from | What the page shows |
|---|---|
| "someone should probably loop in legal about the data side" | ⚠️ no owner named in the transcript |
| "I'll try to get those over to you, but no promises this week" | ⚠️ soft commitment, may not happen |
| "Someone will set that up. Probably after the board meeting" | ⚠️ no owner named; soft commitment |
| Priya's "Will do." to the revised-quote request | ⚠️ owner inferred; supporting quote too short to verify |

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
2. **It's a Business-plan feature.** My own workspace is on Notion's **Free** plan, and the `/meet` block still showed up with a "Start transcribing" button. According to third-party reviews, though, AI Meeting Notes isn't included on Free: using it goes through a 30-day Business trial (card required, capped at 10 hours of meeting notes per user per day), and after that it needs the Business plan (~$20–24/user/month, billed annually). I couldn't confirm the exact trial terms on Notion's own pricing page. Many businesses this size are on Free or Plus and won't pay for Business across the team just for notes. This workflow costs **about 1–1.5 cents per meeting** and needs no plan upgrade.
3. **It handles one meeting at a time, not a batch.** You can't point the built-in feature at a backlog of old transcripts and catch them all up at once. This workflow takes a whole folder in one command, and re-running the folder skips anything already imported.

So to be honest about it: Notion already solved this for Business-plan teams who record live in its desktop app. This build is for everyone else: teams on cheaper plans, or using whatever call tool they already have, who have a transcript and want it turned into structured Notion notes without copying, pasting and reformatting by hand.

---

## 3. The workflow — what / why / how

### What it does

You point `/meeting-notes` at a transcript file, several files, or a whole folder. For each one, Gemini 3.8 Flash pulls out the title, date, attendees, a short summary, decisions and action items, and a new page appears in the team's Notion `Meeting Notes` database. Every action item's owner is checked against the transcript's actual words. Anything not clearly backed is marked **⚠️ Please verify** with the reason, and the page's `Needs review` box is ticked, so it stands out in the database view.

`[SCREENSHOT: the Notion Meeting Notes database after the recorded run, showing both rows with Name, Attendees, Date (blank for Ridgeline), Needs review ticked and Source filled in; the empty Content hash column can be hidden from the view]`

### Why this approach

**A skill plus a small package, not a hosted app.** The assignment rules out servers and frontends, and this doesn't need one: transcripts already sit on someone's laptop or in a synced folder. The skill (`SKILL.md`) is the entry point in Claude Code. The work is done by a small standard-library Python package, so there's nothing to install and nothing to deploy, and the same command runs on its own from any terminal or scheduler.

**Gemini does the extraction, not Claude.** The Claude Code skill only finds the transcript, runs the command and reports back. `SKILL.md` explicitly tells Claude not to write or "improve" the notes. If Claude summarized the transcript itself, the Part 1 capability wouldn't be doing the work, and every run would pay agent-model prices instead of Flash prices.

**Notion's REST API, not the Notion MCP server.** With MCP, an agent model decides what to send to Notion on every run, so the page layout can vary from run to run, and each write goes through another model call. With the REST API, code builds the exact same page structure every time (callout, headings, bullets, a 5-column table), and I could test it with made-up data without spending any Gemini quota. The MCP server also wasn't new enough to count as the Part 1 capability. **What it cost me:** writing the page-building code myself and handling Notion's limits (2,000 characters per text item, 100 blocks per request, table rows created together with the table).

**A fixed JSON schema, not free text.** Gemini is called with `responseMimeType: application/json` and a `responseSchema`, so it can only return the fields the page needs. The code still normalizes the answer (dropping malformed entries, treating an unknown owner status as unassigned), because a schema narrows the output but doesn't guarantee it.

**Check owners in code, not by trusting the model.** Gemini labels each owner `explicit`, `implied` or `unassigned`, but the three-run comparison above shows those labels aren't stable. So the code independently checks each owner against the transcript (step 5 below).

**Built to be maintained, not just demoed.** Once it worked, I restructured it the way I'd want to inherit it: separate modules for configuration, the Gemini client, the Notion client, transcript handling, verification and the CLI; an offline test suite of 81 tests that never calls an API; a CI workflow that runs them on Ubuntu and Windows; clear exit codes; and error messages that say what to do next. It's still standard library only. See [README.md](README.md) for the full layout.

**Tradeoffs I accepted:**
- **It runs when someone invokes it**, not automatically after every call (see interview question 5 for how I'd automate it).
- **It needs an existing transcript.** It doesn't record or transcribe audio.
- **It's built on a days-old model.** On the free tier, testing hit `503 high demand` repeatedly and ran out of quota at 20 requests. Turning on billing fixed it immediately, so a real deployment needs a billed Google Cloud project.
- **It can't catch items the model leaves out,** only check the ones it returns.

### How it works (step by step)

1. **A transcript lands in `transcripts/`.** It can be a Zoom/Teams export (`[00:01:02] Name: text`) or an Otter export (a `Name  0:12` line, then the text), in UTF-8, UTF-16 or Windows-1252. If someone pastes a transcript into Claude Code instead, the skill saves it to `transcripts/pasted-<timestamp>.txt` first. Only files named `sample-*` are committed to git; everything else in that folder stays local, because real transcripts contain client data.

2. **`/meeting-notes transcripts/` runs one command.**
   ```bash
   python .claude/skills/meeting-notes/meeting_notes.py transcripts/
   ```
   It loads settings from `.env`, then makes **one Notion call up front** to confirm the database exists, the connection can see it, and every column is there with the right type. A broken setup fails right away with exit code 2, before any Gemini tokens are spent. A new database is set up once with `--init-db`, which adds the missing columns and never changes existing ones.

3. **Cheap checks come before any API call.** Empty files, files with fewer than 40 words, and files that are mostly symbols are skipped locally. Each transcript is then fingerprinted (a SHA-256 of its content), and if that fingerprint is already in the database's `Content hash` column, the file is skipped, so re-running a folder never creates duplicates. Two different transcripts that happen to share a filename are no longer confused; pages imported before the hash existed are matched by filename instead.

4. **Gemini 3.8 Flash extracts the notes.** The call carries a system prompt with the rules (only use what's in the transcript; follow hand-offs to the person who actually ends up responsible; mark "someone should…" as unassigned; copy the evidence word for word from a single speaker's line), the JSON schema, and `thinkingLevel: low`. For each action item it returns `task`, `owner`, `owner_status`, `evidence`, `due` and `soft_commitment`. It can also answer `is_meeting_transcript: false`: a recipe I fed it came back as *"a baking recipe and not a conversation or meeting transcript"* and was skipped. If Gemini is overloaded, the client retries twice, 20 and 40 seconds apart, and says so on screen.

5. **The code checks every owner against the transcript.** It splits the transcript into who-said-what, handling both the Zoom and Otter formats. An action item is marked **⚠️ Please verify** if any of these is true:
   - no owner is named, or the owner is only inferred
   - the quoted evidence doesn't appear word for word in the transcript (a hallucinated or paraphrased quote)
   - the quote is too short to prove anything (e.g. "Will do.")
   - the quote exists, but it wasn't said by, or to, the named owner (a misattribution)
   - it's a hedged promise ("I'll try, no promises")

   Gemini made no misattributions in testing, so I tested this check directly with deliberately wrong owners, a hand-off, an invented quote and a too-short quote, in both transcript formats. Those cases are part of the test suite.

   `[SCREENSHOT: terminal output of python -m unittest -v, ending with "Ran 81 tests" and "OK"]`

6. **The Notion page is created** with one `POST /v1/pages` call:
   - **Properties:** the title, `Date` (only if the transcript states it; otherwise left blank and listed as an assumption), `Attendees`, `Needs review`, `Source` and `Content hash`
   - **Body:** a ⚠️ callout ("3 of 8 action items need a human check…"), Summary, Attendees, Decisions, an **Action items table** (Task · Owner · Due · Status · From the transcript), the assumptions Gemini made, and a footer with the model name and token counts. Long lists are capped at 25 entries with a "more" note, so a long meeting can't exceed Notion's 100-block request limit.

   `[SCREENSHOT: the top of the BrightPath page from the recorded run: the yellow callout "3 of 8 action items need a human check", Summary, Attendees and Decisions]`
   `[SCREENSHOT: the BrightPath action-items table, with the ✅ rows and the ⚠️ Please verify rows (revised quote, analytics logins, legal) visible]`

7. **A batch summary prints at the end,** including each file's cost. If Gemini is overloaded or out of quota, the batch stops and marks the remaining files "not run", instead of burning requests on each one. Running it again later picks up where it stopped. The exit code is 0 when everything was created, skipped or previewed, and 1 if any file failed, so a scheduler can tell.

   `[SCREENSHOT: the terminal after the recorded run, showing the extracted notes for both files, the ⚠️ please-verify lines, the cost per file ("~$0.0057", "~$0.0024"), the "created" links and the "Done: 2 file(s)" summary]`

`[GIF: one continuous clip with the terminal and Notion side by side: typing python .claude/skills/meeting-notes/meeting_notes.py transcripts/, the notes and cost printing for each file, both rows appearing in the Notion database, then opening the BrightPath page and scrolling to the ⚠️ Please verify rows]`

The recording runs the command directly from a terminal. The `/meeting-notes` skill is a thin wrapper that runs this exact command, so the output is identical.

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
| Gemini paraphrases, stitches or shortens its evidence | Flagged "supporting quote not found" or "too short to verify", even when the owner is right |
| The same transcript, different answers on each run | Flags come from the code check, not the model's label, so every ambiguous item was flagged in all three runs |
| Wrong database ID, or database not shared | Fails before any Gemini call: "Notion: the database isn't visible. Check NOTION_DATABASE_ID…" |
| Invalid Notion token | Fails before any Gemini call: "Notion: the access token was rejected…" |
| Database missing a column | Fails before any Gemini call, naming the columns and pointing to `--init-db` |
| `503 high demand` from Gemini (repeatedly, on the free tier) | 2 retries, 20s and 40s apart, with a visible message; then the batch stops and marks the remaining files "not run". Enabling billing fixed the underlying problem |
| `429` free-tier quota used up (20 requests) | Stops immediately, since retrying can't help |
| Re-running a folder | Transcripts already imported are skipped by content hash (or filename, for older pages); `--force` re-imports |
| A file that can't be read (hit a Windows 260-character path limit) | That file is marked failed; the rest of the batch continues |

`[SCREENSHOT: the terminal with both overloaded runs, one above the other: the first (old code) failing both files with no retries shown, and the second (new code) showing "Gemini busy (503), retrying in 20s (1/2)", "retrying in 40s (2/2)", then Ridgeline marked "not run"]`

---

## 4. Other capability-to-pain-point pairings I considered

*(based on research into what shipped recently, as of mid-September 2026)*

| Capability | Type | Pain point it could solve | Why I didn't build this one |
|---|---|---|---|
| Official Notion MCP server | New connector | Meeting notes / onboarding / dashboards: anything that writes into Notion | I checked its release date and it isn't actually new. It first shipped in April 2025, with a "3.5" feature update in May 2026, so it misses the assignment's "last few weeks" bar for Part 1. Notion stays in the build only as the destination tool, called through its plain REST API, not as the Part 1 capability |
| Notion's built-in AI Meeting Notes (`/meet`) | Existing built-in feature, not something to build | The same pain point: meeting notes never get written up | Not a "capability I spotted", since it already exists and isn't new. I'm naming it because it's the obvious "why build this yourself?" question. It captures live, in the desktop app, and ongoing use needs Notion's Business plan. My build covers existing transcripts and cheaper plans, so I treated it as the competitor to set this apart from, not a pairing to build |
| DeepSeek V4.1 Flash (Sept 10, 2026) | New model | The same task, at the lowest price | DeepSeek's Flash series costs $0.15 input / $0.60 output per 1M tokens off-peak (double at peak), roughly 3–6x cheaper than Gemini 3.8 Flash per call. I nearly switched to it mid-build when Gemini's free tier kept failing. Two things stopped me: DeepSeek's prepaid credit can take 24–72 hours to clear, which was too slow for the deadline, and moving to its OpenAI-style API meant rewriting and re-testing the extraction call. Turning on Gemini billing fixed the reliability problem the same day with no code changes |
| Claude Fable 5.1 (Anthropic, Sept 1, 2026) | New model | The same task, with stronger reasoning | Same headline price as GPT-6 Astra ($10/$50 per million tokens), about $0.19 for a 45-minute call, around 13x Gemini 3.8 Flash's cost, for a task that's structured extraction, not deep reasoning. Ruled out on cost per run for a workflow meant to run on every call |
| GPT-6 Astra (OpenAI, Sept 3, 2026) | New model | Drafting personalized replies to leads from form submissions | More reasoning power than this task needs, the same cost problem as Fable 5.1 above, and it would add a second provider and API key to the workflow |
| Meta Muse Spark 1.3 (Sept 2, 2026) | New model | The same meeting-notes extraction, through its low-cost endpoint | Its standard endpoint ($1.25 / $4.25 per 1M tokens) costs more than Gemini 3.8 Flash. Its much cheaper "contributor" endpoint (~$0.10 / $0.20) lets Meta train on your traffic, which rules it out for client call transcripts. And 1.3's improvements are in agentic coding (about 20% fewer tool calls than 1.2), not extraction |
| Slack native MCP support | New connector | A DM or comment sits unanswered for hours | Real ICP pain, but testing the native MCP path needs a live Slack workspace on Business+ or Enterprise, which is hard to demo end to end in 1–3 days on a personal account |
| Salesforce Agentforce named agents (Sept 11, 2026) | New agent product | Several ICP pains at once (sales, service, support) | It's a full platform, not something I can wire together myself in a small script, which goes against the assignment's "not a hosted application" rule |

---

## 5. Likely interview questions

1. **Doesn't Notion already do this natively with its AI Meeting Notes feature?**
   Partly, and I checked before building. Notion's `/meet` records a call live in the desktop app and writes a summary with action items. It does that well if you're on the Business plan and remember to start it before the call. On Free, it's only available through a Business trial. What it doesn't do is take the transcripts a business *already has* (Zoom, Teams, Otter), process a backlog of them in one go, or check who actually owns each task. My build covers exactly that gap, at about a cent per meeting, for teams that won't upgrade everyone to Business just for notes.

2. **Why did you pick a Flash-tier model instead of a flagship one?**
   Because this runs on every call, and the task is extraction, not reasoning. From real token counts, a 45-minute call is about 9,000 tokens in and 2,000 out: roughly $0.19 at flagship prices vs about $0.014 on Gemini 3.8 Flash, around 13x cheaper. Across three runs it never assigned a task to the wrong person, including two deliberate traps. Its real weakness was consistency: the same transcript produced different confidence labels, and once it left out a task entirely. I didn't rely on the cheaper model being right; owners are checked in code afterwards.

3. **What happens if the transcript is garbled or the call was cut short — does the skill fail gracefully?**
   Yes, and each case is covered by a test. Empty, too-short (under 40 words) and mostly-symbol files are skipped locally before any API call. Text that isn't a meeting gets rejected by Gemini itself: I fed it a recipe and it came back `is_meeting_transcript: false`, with nothing written. A cut-short call that's still a real conversation gets processed, with whatever decisions and items it actually contains. Anything missing, like the date, is left blank and listed under "Assumptions made" rather than invented. In a batch, one bad file never stops the others.

4. **Why call Notion's REST API directly instead of using the Notion MCP server — and why not a visual/no-code tool?**
   Predictability and testability, both times. With MCP, a model decides what to write on every run, so the page structure can drift, and every write costs another model call. With the REST API, code builds the same page every time, and I can test the exact payload offline, including Notion's limits. The MCP server also wasn't new enough to count as the Part 1 capability. A no-code tool is ruled out by the assignment, but it would also have been the wrong fit: the owner check splits a transcript by speaker and matches quotes, which is awkward to build in visual nodes and impossible to unit-test. In code, `python -m unittest` runs 81 checks in under a second.

5. **Why a Claude Code skill instead of a scheduled job — and how would you make it run automatically after every call?**
   For a first version, a person looking at the output is a feature: the ⚠️ items need someone to check them anyway, and the skill also handles "here, I'll paste this transcript". But the logic is a plain command with exit codes, so automating it is configuration, not a rewrite. Most call tools can save transcripts to a synced folder (Zoom cloud recordings, a shared Google Drive or OneDrive folder). I'd schedule the same command against that folder every 15 minutes with Windows Task Scheduler or cron. Re-runs are safe because imported transcripts are skipped by content hash, and a Gemini outage just stops the batch for the next run to pick up. The fully push-based version, where Zoom notifies you the moment a transcript is ready, needs a small hosted endpoint; that's outside this assignment's rules, but it would be the production step.

6. **What's the caveat you designed around, how does the safeguard work, and how did you know the output was right?**
   Misattribution: Flash-tier models can get a task right but pin it on the wrong person. There are two layers. Gemini has to label each owner and copy the exact words where the commitment was made; then the code ignores that label and checks the quote really exists, is long enough to mean something, and was said by or to the named owner. Anything that fails, or is implied, unassigned or hedged, becomes "⚠️ Please verify: <reason>" and ticks `Needs review`. To validate it, I wrote the test transcripts myself with known answers and traps, ran them three times and compared line by line: zero wrong owners, every ambiguous item flagged, one omission. I also tested the check directly with deliberately wrong owners, a hand-off and an invented quote. The honest limit is that it can't flag a task the model never returned, and two transcripts is a small sample.

7. **Why this pain point specifically, out of the six the assignment listed?**
   It happens on every client call, so it's constant, not occasional. The cost of missing it is concrete: a forgotten follow-up is a lost deal or an unhappy client. It maps cleanly onto what a cheap, fast model does well. And it has a clear before and after you can verify: either the action items with owners are in Notion, or they aren't.

8. **What would break first if 50 people at a company used this simultaneously?**
   **Gemini capacity and rate limits come first,** and I hit both with just one user on the free tier: repeated `503 high demand`, then a 20-request cap. Billing fixed that for one person, but at team scale you'd still want a queue that spreads requests under the paid rate limits, plus a fallback model for demand spikes on a brand-new model. **Next is Notion's rate limit,** since everyone shares one connection token and each file makes about three Notion calls. **Then key management:** one token copied into everyone's `.env` is fine for a prototype, not for 50 people. You'd want a shared runner with the secrets in one place. One thing that *wouldn't* break: two people importing different transcripts both called `call.txt`, because duplicates are detected by content, not filename.

9. **What would this actually cost a business running it at real volume — say 20 calls a week?**
   At 45 minutes a call, that's 180,000 input and 40,000 output tokens a week: 0.18 × $0.75 + 0.04 × $3.75 ≈ **$0.29 a week, or about $1.23 a month** at Gemini 3.8 Flash's 2026 rates, and about $2.45 a month once Google doubles them in 2027. The same volume at flagship prices is about $16 a month. Notion's API is free on any plan, and there's no hosting cost because nothing is hosted.

10. **If you had another week, what would you build next — and what would you do differently?**
    **Next:**
    - **An evaluation set** of 20–30 anonymized real transcripts with hand-labelled owners, run several times each. That would measure wrong-owner rate and omission rate, and compare Flash with a flagship on data instead of a hunch.
    - **Catch omissions,** the gap the safeguard can't cover. For example, a second cheap pass that lists every commitment-like sentence ("I'll…", "can you…", "someone should…") and flags any the extraction didn't account for.
    - **Close the loop on ⚠️ items:** post each one to the relevant person in Slack, and link owners to real Notion users.

    **Differently:** I'd start on a billed project from day one. The free tier's overload and quota limits cost me more time than any code did. I'd also run each test transcript several times from the start: a single clean run made the model look more consistent than it is.

---

## 6. Appendix — raw research notes

Capabilities that shipped in the ~2 weeks before this build (for reference and as an audit trail):
- Sept 1, 2026: Claude Fable 5.1 and Mythos 5.1 (Anthropic)
- Sept 2, 2026: Gemini 3.8 Flash + gated Cyber variant (Google); Muse Spark 1.3 (Meta)
- Sept 3, 2026: GPT-6 Astra (OpenAI)
- Sept 10, 2026: DeepSeek V4.1 Flash
- Sept 11, 2026: Fugu Ultra v2.0 and Fugu Max (Sakana AI); Salesforce Agentforce named agents
- Ongoing: Slack native MCP support (Business+/Enterprise); official Notion MCP server; Hex as an MCP client

Sources checked:
- Release timelines: LLM Gateway release timeline, Capital & Compute model tracker, Agentic.ai news, AI Agent Store weekly digest.
- Pricing: [Gemini API pricing page](https://ai.google.dev/gemini-api/docs/pricing) (Gemini 3.8 Flash paid tier: $0.75 / $3.75 per 1M tokens through Dec 31, 2026, then $1.50 / $7.50); the per-token pricing pages for Claude Fable 5.1 and GPT-6 Astra; DeepSeek's top-up page (Flash series: $0.15 / $0.60 per 1M off-peak, double at peak; credits can take 24–72 hours to clear).
- Muse Spark 1.3: [Bloomberg](https://www.bloomberg.com/news/articles/2026-09-02/meta-releases-more-powerful-ai-model-edging-closer-to-rivals), [MarkTechPost](https://www.marktechpost.com/2026/09/03/meta-ai-released-muse-spark-1-3-an-agentic-coding-model-that-uses-20-fewer-tool-calls-and-25-fewer-tokens-than-muse-spark-1-2/), [eesel AI](https://www.eesel.ai/blog/muse-spark-1-3) (pricing, contributor endpoint, coding focus).
- Notion: the official MCP server changelog and GitHub repo, which confirmed it was *not* recent enough for Part 1 (first shipped April 2025, "3.5" update May 2026). For AI Meeting Notes plan availability and the 30-day Business trial: [tl;dv review](https://tldv.io/blog/notion-ai-meeting-notes-review/) and [Lifestack's Notion pricing guide](https://lifestack.ai/blog/notion-pricing). Both are third-party sources.

---

## 7. Build log

- **Step 1: Scaffold.** Created the project folder with README, `.env.example`, `.gitignore` (ignores `.env` and every transcript except `sample-*`), a `/transcripts` folder, and this document. Chose plain Python with only the standard library (`urllib`) so there's nothing to install and the whole flow is two kinds of HTTP call you can read.
- **Step 2: API access.** Created a Notion connection (Developer tools → Connections → New connection) using **Access token** auth, scoped to one workspace, with only Read/Update/Insert content and **no user information**, so it gets the least access it needs. Notion had renamed "integrations" to "connections" since most tutorials were written, so `.env.example` points to the new location. Created an empty full-page `Meeting Notes` database (deliberately *not* Notion's "Meeting Notes" template, which sets up Notion's own AI Meeting Notes) and shared only that database with the connection. Then, through the API, found the database ID and added the columns the skill writes: `Date` (so notes sort and filter by meeting date), `Attendees`, `Needs review` (ticked when any action item has an unconfirmed owner, so the safeguard is visible from the database view without opening each page), and `Source` (the transcript filename). Notion test call: created a throwaway page in the database. Gemini test call: created a free-tier API key in Google AI Studio and sent a trivial prompt to `gemini-3.8-flash`, which answered correctly. Usage came back as 9 prompt tokens, 4 output tokens **and 98 "thinking" tokens**: even a one-line reply triggered hidden reasoning, and thinking tokens are billed as output. So the extraction call sets a low thinking level. Testing was done with fictional transcripts, because free-tier inputs may be used by Google to improve its products.
- **Step 3: Build and first tests.** Built the skill as `SKILL.md` plus one standard-library Python script. Dry runs on both fictional transcripts got every action-item owner right, including a deliberate trap (Mark is asked about the brand guidelines via Sarah and ends up owning them) and a hand-off (Daniel passes the sitemap to Aisha, and Priya ends up owning "ask Aisha"). Every vague item was flagged. Gemini made no misattributions, so I tested the code-level owner check separately by feeding it deliberately wrong owners and an invented quote: it caught all 4 bad items, passed all 3 correct ones, and worked on both Zoom-style and Otter-style transcripts. With `thinkingLevel: low`, thinking tokens dropped from 98 on the test call to 0 on real transcripts. Local checks skipped empty, too-short and garbled files before any API call, and a wrong database ID or bad Notion token failed before any Gemini tokens were spent. Before the first live write, I checked the Notion page format with made-up notes (no Gemini call).
- **The free tier fell over during testing, which is a real finding.** A new model on the free tier is fragile. I hit repeated `503 high demand` errors, then `429 quota exceeded` at **20 free-tier requests** for `gemini-3.8-flash`. The first batch attempt failed on both transcripts, and the original retry loop (5 tries per file) spent about 10 of the 20 free requests without producing anything. I changed three things: (1) only 2 retries, 20s and 40s apart, since failed calls can still count against quota; (2) the script prints "Gemini busy, retrying in 20s" so a wait doesn't look like a hang; (3) a batch stops at the first overload or quota failure and marks the remaining files "not run". The next real attempt hit the same overload and behaved exactly that way, using 3 requests instead of 10.
- **Step 4: First real end-to-end run.** The free tier stayed overloaded, so I weighed two fixes. DeepSeek V4.1 Flash was cheaper, but its prepaid credit could take up to 72 hours to clear, too slow for the deadline, and switching would have meant rewriting the extraction call. Enabling billing on the existing Google Cloud project was the lower-risk fix: same API key, active immediately, no code changes. Paid tier went straight past the overload and created both Notion pages, which I read back through the API to confirm the structure (BrightPath: 8 action items, 4 flagged; Ridgeline: 3 action items, 2 flagged, `Date` blank because the transcript states none). The owner check fired on real extractions: it flagged two items where Gemini paraphrased or stitched its evidence, even though both owners were correct. After screenshots, both pages were moved to Notion's trash so the run could be recorded from a clean database.
- **Step 5: Recorded run.** Re-ran the same command on camera, now printing each file's cost (~$0.0057 and ~$0.0024). Gemini's answers differed from run 1 on the same transcripts: a different wording of the Dentrix sign-off step, 4 decisions instead of 5, and Ridgeline's "check with finance" changed from "Tom, inferred" to "Unassigned". It still assigned no task to the wrong person, and every ambiguous item was flagged, which is the comparison in section 1.
- **Step 6: Production hardening.** Restructured the working prototype so it's maintainable, keeping it standard library only and keeping the recorded command identical:
  - **Structure:** split the 470-line script into the `src/meeting_notes` package (config, API helper, Gemini client, Notion client, transcript handling, verification, CLI). The skill's script is now a short entry point that only puts the package on the path, and `pyproject.toml` provides an optional `meeting-notes` command.
  - **Tests and CI:** 81 offline tests (injectable HTTP, sleep and output, so retries, failures and batch behaviour are tested without any API), and a GitHub Actions workflow running them on Ubuntu and Windows with Python 3.9 and 3.13.
  - **Bugs fixed:** missing fields in a model answer could share default lists between transcripts in the same batch; a page with very long lists could exceed Notion's 100-block request limit; transcripts in scripts like Devanagari could be rejected as garbled.
  - **Weaknesses addressed:** duplicate detection moved from filename to a content hash (with a filename fallback for existing pages); `--init-db` sets up the database's columns so nobody repeats my manual API calls; verification now also flags quotes too short to prove anything; the prompt asks for evidence from a single speaker line after run 1 showed stitched quotes; `GEMINI_MODEL` makes the model configurable; setup problems exit with code 2 and messages that name the fix.
  - **Verified live:** `--init-db` added the `Content hash` column; a real run then skipped both existing pages by filename with zero Gemini calls; and a paid dry run (run 3, ~$0.008 total) confirmed the refactored extraction path. In run 3 the new rule flagged Priya's "Will do." as too short to verify, and Gemini left out the "check with finance" task entirely, which is the omission limit described in section 1.
