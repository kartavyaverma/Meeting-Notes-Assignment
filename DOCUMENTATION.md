# AI Engineer Intern Assignment — Documentation

---

## 1. The capability I spotted

**Capability:** Gemini 3.8 Flash (Google), released September 2, 2026, well within the assignment's "last few weeks" window. The build uses it directly as the model that reads a raw call transcript and pulls out structured meeting notes (attendees, decisions, action items).

**Why this counts as "new":** It has a specific, checkable release date (September 2, 2026). It isn't a general capability I already knew about. It's also the actual reasoning engine inside the workflow, not just the tool I used to write the code.

**Why this model instead of a flagship one:** This is a frequent, simple extraction task: every client call a business takes produces one. A flagship model (e.g. GPT-6 Astra or Claude Fable 5.1) costs roughly $0.15–0.20 per call at published rates. Gemini 3.8 Flash costs roughly $0.01–0.02 per call, 15–25x less, and the job is structured extraction, not deep multi-step reasoning. For a 50–300 person business running this on every client call, that gap adds up. Choosing the cheapest model that still does the job correctly is the right call for a workflow that repeats this often. [FILL: replace the estimate with the per-run cost measured from real token usage during testing.]

**The caveat I designed around:** Flash models give up some reasoning depth in exchange for speed and low cost. The real risk isn't total failure. It's **misattribution**: getting a decision or action item right but giving it to the wrong person, or missing a softer commitment ("I'll try to get that over" vs. an explicit "I will do X by Friday") that a stronger model might catch. So the build doesn't blindly trust every extracted action item. When the transcript doesn't explicitly name an owner, the output marks the item "please verify" instead of guessing. [FILL: note here whether you actually saw a misattribution during testing, and what the flagged output looked like.]

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
2. **Ongoing use is tied to Notion's paid AI plans.** I tested this myself: my workspace is on the **Free** plan and the `/meet` block still appeared with "Start transcribing", so Notion lets Free users *try* it. Continued use is part of Notion's Business plan (~$20–24/user/month, billed annually). [VERIFY on notion.com/pricing before submitting: the exact Free-plan trial limit for AI Meeting Notes.] Many businesses this size are on Free or Plus and won't pay for Business across the team just for notes. This workflow costs a measured fraction of a cent to a few cents per meeting (see the cost section) and needs no plan upgrade.
3. **It handles one meeting at a time, not a batch.** You can't point the built-in feature at a backlog of old transcripts and catch them all up at once. This workflow processes any transcript file you give it, whenever the call was recorded.

So to be honest about it: Notion already solved this for Business-plan teams who record live in its desktop app. This build is for everyone else: teams on cheaper plans, or using whatever call tool they already have, who have a transcript and want it turned into structured Notion notes without copying, pasting and reformatting by hand.

---

## 3. The workflow — what / why / how

### What it does
[FILL: 2-3 sentence plain description of the finished skill, once built.]

### Why this approach
[FILL: Why a Claude Code skill that calls the Gemini API and Notion's REST API directly, instead of e.g. a cron script, a hosted webhook, or the Notion MCP server. What did calling the REST API directly buy you (no extra server process, exact control over block formatting)? What tradeoff did you accept (e.g. it only runs when invoked manually, not on a schedule)?]

### How it works (step by step)
1. [FILL: e.g. "A transcript file is dropped in /transcripts or pasted into the terminal."]
2. [FILL: "The script sends it to Gemini 3.8 Flash, which returns JSON: title, date, attendees, decisions, action items."]
3. [FILL: "The script validates the JSON and flags action items without an explicitly named owner."]
4. [FILL: "The script calls Notion's REST API to create a page in the connected database, formatted with headings and an action-items table."]

`[SCREENSHOT: Google AI Studio showing the Gemini API key created (key value blurred)]`
`[SCREENSHOT: the terminal showing the successful test call to gemini-3.8-flash]`
`[SCREENSHOT: the Notion connection settings page (Developer tools → Connections → Meeting Notes) showing Access token auth, Read/Update/Insert content enabled, and the token hidden as dots]`
`[SCREENSHOT: the Meeting Notes database's ••• → Connections menu showing the Meeting Notes connection added]`
`[SCREENSHOT: the terminal running the /meeting-notes skill against a real transcript]`
`[SCREENSHOT: the finished Notion page it created]`
`[GIF: the whole run, from pasting the transcript to the Notion page appearing, in one continuous clip]`

---

## 4. Other capability-to-pain-point pairings I considered

*(based on research into what shipped recently, as of mid-September 2026)*

| Capability | Type | Pain point it could solve | Why I didn't build this one |
|---|---|---|---|
| Official Notion MCP server | New connector | Meeting notes / onboarding / dashboards: anything that writes into Notion | I checked its release date and it isn't actually new. It first shipped in April 2025, with a "3.5" feature update in May 2026, so it misses the assignment's "last few weeks" bar for Part 1. Notion stays in the build only as the destination tool, called through its plain REST API, not as the Part 1 capability |
| Notion's built-in AI Meeting Notes (`/meet`) | Existing built-in feature, not something to build | The same pain point: meeting notes never get written up | Not a "capability I spotted", since it already exists and isn't new. I'm naming it because it's the obvious "why build this yourself?" question. It captures live, in the desktop app, and needs Notion's Business plan. My build covers existing transcripts and cheaper plans, so I treated it as the competitor to set this apart from, not a pairing to build |
| Claude Fable 5.1 (Anthropic, Sept 1, 2026) | New model | The same task, with stronger reasoning | Same headline price as GPT-6 Astra ($10/$50 per million tokens), roughly 15–25x more than Gemini 3.8 Flash for a task that's structured extraction, not deep reasoning. Considered, then ruled out on cost per run for a workflow meant to run on every call |
| GPT-6 Astra (OpenAI, Sept 3, 2026) | New model | Drafting personalized replies to leads from form submissions | More reasoning power than this task needs, the same cost problem as Fable 5.1 above, and it would add a second provider and API key to the workflow |
| Slack native MCP support | New connector | A DM or comment sits unanswered for hours | Real ICP pain, but testing the native MCP path needs a live Slack workspace on Business+ or Enterprise, which is hard to demo end to end in 1–3 days on a personal account |
| Meta Muse Spark 1.3 (Sept 2, 2026) | New agent model | [FILL if explored further] | Less documentation on what actually changed in 1.3 vs 1.2, so more research risk for a 1–3 day build |
| Salesforce Agentforce named agents (Sept 11, 2026) | New agent product | Several ICP pains at once (sales, service, support) | It's a full platform, not something I can wire together myself in a small script, which goes against the assignment's "not a hosted application" rule |

---

## 5. Likely interview questions

1. **Doesn't Notion already do this natively with its AI Meeting Notes feature?**
   [FILL]
2. **Why did you pick a Flash-tier model instead of a flagship one?**
   [FILL]
3. **What happens if the transcript is garbled or the call was cut short — does the skill fail gracefully?**
   [FILL]
4. **Why call Notion's REST API directly instead of using the Notion MCP server?**
   [FILL]
5. **Why a Claude Code skill instead of a scheduled/cron job?**
   [FILL]
6. **How would you turn this into something that runs automatically after every call, without you manually invoking it?**
   [FILL]
7. **What's the actual caveat you designed around, and how does the safeguard work end to end?**
   [FILL]
8. **Why this pain point specifically, out of the six the assignment listed?**
   [FILL]
9. **What would break first if 50 people at a company used this simultaneously?**
   [FILL]
10. **Why didn't you use a visual/no-code tool — wasn't that faster?**
    [FILL]
11. **How did you validate the output was actually correct and not hallucinated action items?**
    [FILL]
12. **What would this actually cost a business running it at real volume — say 20 calls a week?**
    [FILL: use the per-run cost measured from real token usage]
13. **If you had another week, what's the next thing you'd build on top of this?**
    [FILL]

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
- **Step 2: API access.** Created a Notion connection (Developer tools → Connections → New connection) using **Access token** auth, scoped to one workspace, with only Read/Update/Insert content and **no user information**, so it gets the least access it needs. Notion had renamed "integrations" to "connections" since most tutorials were written, so `.env.example` points to the new location. Created an empty full-page `Meeting Notes` database (deliberately *not* Notion's "Meeting Notes" template, which sets up Notion's own AI Meeting Notes) and shared only that database with the connection. Then, through the API, found the database ID and added the columns the skill writes: `Date` (date, so notes sort and filter by meeting date), `Attendees` (text), `Needs review` (checkbox, ticked when any action item has an unconfirmed owner, so the misattribution safeguard is visible from the database view without opening each page), and `Source` (the transcript filename, so a batch run can be traced back to its file). Notion test call: created a throwaway page `API connection test (safe to delete)` in the database. Gemini test call: created a free-tier API key in Google AI Studio and sent a trivial prompt to `gemini-3.8-flash`, which answered correctly. Usage came back as 9 prompt tokens, 4 output tokens **and 98 "thinking" tokens**: even a one-line reply triggered hidden reasoning, and thinking tokens are billed as output. That matters for cost at volume, so the extraction call will set a low thinking budget. Pulling structure out of a transcript doesn't need much reasoning, and the owner-verification flag covers the one place where weaker reasoning could hurt. Testing was done on the free tier with a fictional transcript, because free-tier inputs may be used by Google to improve its products. Real client transcripts need a billed project.
- **Step 3: Build and first tests.** Built the skill as `SKILL.md` plus one standard-library Python script. Dry runs on both fictional transcripts got every action-item owner right, including a deliberate trap (Mark is asked about the brand guidelines via Sarah and ends up owning them) and a hand-off (Daniel passes the sitemap to Aisha, and Priya ends up owning "ask Aisha"). Every vague item was flagged: "we'll get the quote over" (implied owner), "I'll try, no promises" (soft commitment), "someone should loop in legal" (unassigned). Gemini made no misattributions, so I tested the code-level owner check separately by feeding it deliberately wrong owners and an invented quote: it caught all 4 bad items, passed all 3 correct ones, and worked on both Zoom-style and Otter-style transcripts. Two small misses from Gemini: it didn't list "Daniel sends Sarah the forms to sign" or "set up the Tuesday check-in" as action items. Those are omissions, not misattributions. With `thinkingLevel: low`, thinking tokens dropped from 98 on the test call to 0 on real transcripts. Local checks skipped empty, too-short and garbled files before any API call, and a wrong database ID or bad Notion token failed before any Gemini tokens were spent.
- **The free tier fell over during testing, which is a real finding.** A new model on the free tier is fragile. I hit repeated `503 high demand` errors, then `429 quota exceeded` at **20 free-tier requests** for `gemini-3.8-flash`. Automatic retries on the 503s used up that quota faster, so the script now stops immediately on a quota error instead of retrying. Production use needs a billed project, and ideally a fallback model for demand spikes.
