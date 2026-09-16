# Technical specification
## Adventure story generator agent — file-backed orchestration

| | |
|---|---|
| **Version** | 2.2 |
| **Date** | 16 September 2026 |
| **Implements** | Functional specification v2.2 |
| **Configuration** | `config.json` |
| **Status** | Draft for review |

---

## 1. Scope

The functional specification defines *what* the system produces. This document defines *how*: file layout and formats, the configuration contract, the per-call prompt contracts, context assembly, token and cost budget, validation code and resume.

Each technical requirement (TR-xx) traces to a functional requirement (FR-xx) in section 10.

### 1.1 Change from version 1.x

Version 1.x specified a single-prompt harness in which the transcript was the memory. Its blocking defect was arithmetic: a complete run needed ≈25 000 output tokens **in one response**, so feasibility depended entirely on a single model parameter, and no amount of prompt engineering could move it. Two further properties made it hard to operate — a run could not be resumed, and mechanical validation was the model's report on its own work rather than a measurement.

Moving state to disk retires all three. The cost is an orchestrator that can itself be wrong, and page-to-page continuity that must now be engineered rather than assumed.

### 1.2 Change from version 2.1

Version 2.1 was validated by a complete run, recorded in `report.md`. It produced an acceptable story and exposed four defects in the specifications rather than in the run: a configuration that could not be edited one value at a time, a sheet budget that silently doubled as a cast budget, a summary window that was inert at any chapter length below its own value, and a digest with no bound, which overran the context budget fourfold. It also exposed a gap that had no branch in the flow at all — a continuity defect found after the offending pages were committed — now closed by the chapter-close audit. This version applies all five.

---

## 2. Architecture

```
config.json          ← single source of control and organization values
    │
    ▼
orchestrator ──► model call (Phase A: bible)      ──► bible/*
             ──► model call (Phase B: page N) ×P  ──► pages/NN.md
             ──► deterministic validation (code)   ──► state/deltas.jsonl
             ──► model call (Phase C: report)      ──► report.md
```

The orchestrator owns the loop, the counters, retry, the stop condition and every file write. The model owns prose and narrative judgement, and nothing else.

**TR-01.** The orchestrator shall read every control and organization value from `config.json` at start-up. No such value shall appear as a literal in code or in a prompt template; prompts receive them by interpolation (FR-20).

**TR-02.** The configuration in force shall be copied into the run directory at start-up, so that a completed run carries the parameters that produced it.

---

## 3. Configuration contract

### 3.1 Validation

Checked before the first model call. Failure aborts when `control.abort_on_invalid_config` (FR-21).

| # | Invariant | Failure mode it prevents |
|---|---|---|
| I-1 | `pages_total ≥ 1`, and the derived chapter count lies in `[1, pages_total]` | Empty chapters, or a story with no pages |
| I-2 | `act_proportions` all positive, summing to 1, with `pages_total ≥` the number of acts | An act that cannot be given a single page |
| I-3 | an explicit `anchor_pages` list, where given, lies in `[1, pages_total]` | Anchor beyond the last page |
| I-4 | `world_rules_min ≤ world_rules_max` | Unsatisfiable bible bounds |
| I-5 | `0 < page.length_tolerance < 1` | Length check that can never fail, or never pass |
| I-6 | every path in `paths` is writable | Failure discovered after tokens are spent |
| I-7 | `context.max_characters_per_page ≥` characters declared by any beat, and the same for settings | Context silently truncating a declared character |
| I-8 | `bible.max_characters ≥ context.max_characters_per_page`, and the same for settings | A page whose cast ceiling can never be filled |

I-7 is checked after the beat sheet exists, at the A6 gate, not at start-up.

**The invariants that version 2.1 needed most are gone, because derivation removed the conditions they policed.** `chapters × pages_per_chapter = pages_total` and `sum(acts) = pages_total` were checks on the author's arithmetic, and their only remedy was to abort. Under section 3.1b the same configurations now resolve instead of failing. An invariant that fires whenever a user edits one value is not protecting the system from the user; it is protecting the system from its own schema.

### 3.1b Derivation

Implements FR-36 and FR-37, by the rules of functional specification §2.2.

```
derive(organization):
    P  ← organization.pages_total
    C  ← organization.chapters
          else ceil(P / organization.pages_per_chapter)
          else 1
    if both given and C × pages_per_chapter ≠ P:
          report supersession, keep chapters            # FR-37
    base, rem ← divmod(P, C)
    chapter_sizes ← [base+1] * rem + [base] * (C - rem)
    acts          ← largest_remainder(act_proportions, P, min=1,
                                       ties by declaration order)
    act_spans     ← consecutive spans over acts, in declaration order
    anchor_pages  ← organization.anchor_pages
                     if "auto": first, middle, last page of act "development"
    return chapter_sizes, acts, act_spans, anchor_pages
```

**TR-03b.** Derived values shall be computed at load time and never written back to `config.json`. A derived value stored in the file is a value that can go stale, which is the defect derivation exists to remove.

**TR-03c.** Any value superseded by precedence shall be reported at start-up and recorded in the closing report (FR-37). Silently preferring one of two conflicting values is worse than either honouring or rejecting it: the author sees a run that appears to ignore the file.

### 3.2 Binding

Both specifications reference configuration by path. The orchestrator exposes the parsed config to prompt templates under the same names, so `{{organization.pages_total}}` in a template and `organization.pages_total` in the specification denote one value with one definition.

**TR-03.** Changing the shape of a story shall require editing `config.json` only, **one value at a time**. Editing `pages_total` alone, or `chapters` alone, shall produce a story of the new shape without any other edit to the file. This is the acceptance test for FR-20 and FR-36, and it is the test version 2.1 failed: five interdependent values meant that every single-value edit left the file invalid and, under `control.abort_on_invalid_config`, stopped the run before the first call.

---

## 4. File layout and formats

```
config.json
bible/
  premise.md                conflict, theme, tone, tentative ending
  rules.md                  world rules, one per line
  characters/c1-mara.md     frontmatter + prose
  settings/s2-lighthouse.md frontmatter + prose
  beats.json                one entry per page, looked up by page number
state/
  deltas.jsonl              append-only, one record per completed page
  chapters/02.md            digest, written when chapter 2 closes
pages/
  07.md                     frontmatter + prose
runs/2026-09-15T10-00/
  config.json               the configuration that produced this run
  ctx-07.md                 assembled context, diagnostic only
story.md                    the manuscript, rebuilt from pages/
report.md
```

**Format per category.** Fixed state is Markdown with frontmatter, because a person edits it: machine-checkable fields in the header, prose where prose belongs. The beat sheet is JSON, because its only job is lookup by page number. Mutable state is JSON Lines, because it is append-only and a truncated write loses at most the final record.

```markdown
---
id: c1
name: Mara
role: protagonist
desire: find her brother
fear: deep water
arc: {from: fearful, to: resolute}
---

**Appearance.** A pale scar across the left hand; an oilskin coat two sizes large.

**Voice.** Clipped sentences. No contractions. Answers questions with questions.
```

```json
{"page": 7, "chapter": 2, "chapter_title": "The Cold Lamp",
 "act": "development", "anchor": false,
 "objective": "Mara reaches the lighthouse and finds it abandoned",
 "hook": "the lamp is cold", "characters": ["c1", "c3"], "settings": ["s2"]}
```

```json
{"page":7,"chapter":2,"words":312,"retries":0,"flagged":false,
 "summary":"Mara reaches the lighthouse; it is abandoned and the lamp is cold.",
 "states":{"c1":"at the lighthouse, shaken"},
 "threads_opened":["t4"],"threads_closed":["t2"],
 "facts":["the lamp has been cold for eight days",
          "the reservoir holds eleven casks"],
 "supersedes":null}
```

**TR-04.** Character and setting identifiers (`c1`, `s2`) shall be assigned in Phase A and are immutable; every later reference uses the identifier. This makes an FR-11 violation decidable by set membership rather than by matching names that legitimately vary in prose.

**TR-04b.** Thread identifiers (`t4`) are the exception: threads come into existence during Phase B, so the orchestrator mints the identifier at the moment a thread opens, in the same state record (FR-35). Threads are never pre-declared in Phase A, because a beat sheet cannot know which promises the prose will actually make.

**TR-04c.** `facts` carries the concrete assertions of the page — dates, counts, quantities, the names of places and objects (FR-38). Replayed across the log it is the fact ledger the chapter-close audit reads. `supersedes` names the earlier record a continuity repair replaces (FR-40), so that a replay can prefer the repair without the duplicate-record anomaly that TR-18 otherwise has to absorb.

**TR-05.** Every write shall be atomic — written to a temporary file and renamed — so that an interrupted run never leaves a half-written page or state record (FR-24).

**TR-06.** The run directory shall be write-only from the orchestrator's perspective: nothing under `paths.runs_dir` is ever read back as state (FR-26).

---

## 5. Per-call contracts

Four call types, each with its own system prompt. They are enumerated as agents in section 12.2.

| Call | Input | Output | Frequency |
|---|---|---|---|
| Bible | Premise, `story`, `organization`, `bible` bounds | Rules, characters, settings, beat sheet | Once |
| Page | Assembled context (section 6) | Prose of one page | `pages_total`, plus retries |
| Consistency | The finished page, its sheets, rules and objective | Structured verdict | Once per page attempt |
| Audit | Beat sheet, state log, arcs | Report content | Once |

**TR-07.** The page call shall receive the page objective and hook as data, never as an invitation to reinterpret them. The beat sheet is authoritative; the page call has no licence to change it. Deviations go through FR-18, which is an orchestrator-mediated rewrite of the remaining entries.

**TR-08.** The page call shall return prose only. Structure, numbering and frontmatter are added by the orchestrator, so nothing the model emits can corrupt the file layout.

**TR-09.** The consistency check shall be issued as a separate call taking the finished page as input, never appended to the call that wrote it. A model asked to grade its own output in the same turn approves it. This is the mechanism that retires the principal risk of v1.x, and it is the reason OI-05 must close before approval.

**TR-10.** Temperature shall differ by call type: `model.temperature` for the page call, and 0 for the audit and consistency calls, which are judgements rather than compositions.

---

## 6. Context assembly

Deterministic, executed by the orchestrator, no model involvement.

```
assemble(N):
    voice   ← story.tone, story.audience, story.language
    beat    ← beats[N]
    rules   ← read(paths.world_rules)
    chars   ← [read(c) for c in beat.characters]
    sets    ← [read(s) for s in beat.settings]
    assert len(chars) ≤ context.max_characters_per_page
    assert len(sets)  ≤ context.max_settings_per_page
    digests ← [read(chapters/c) for c in closed chapters before beat.chapter]
    recent  ← summaries of the last context.verbatim_summary_window pages,
              kept even where their chapter is digested          # FR-41
    bridge  ← final paragraph of pages/(N-1).md   if context.include_bridge_paragraph
    return render(voice, rules, chars, sets, beat.objective, beat.hook,
                  beat.anchor, digests, recent, bridge)
```

**TR-10b.** `voice` is not decoration. `story.tone` and `story.audience` reach Phase A through the bible call, but without this line they never reach the twenty calls that write the actual prose, and the run produces a correctly structured story in the wrong register (FR-31). `story.language` travels with them for the same reason (FR-30).

**TR-10c.** The two sheet ceilings shall be enforced separately. A single shared budget makes the cast size of every scene a function of how many settings the beat declares: at a budget of three, any page with a setting is a two-hander. The first run was written entirely in two-handers for exactly this reason, and nothing in either specification predicted it.

**TR-11.** Character states in the context shall come from the **last** record in `deltas.jsonl` that mentions each character, not from the sheet, whose `state` is the Phase A value. The sheet holds what is immutable; the log holds what has happened.

**TR-12.** A page whose beat opens a chapter shall receive the previous chapter's digest in place of a bridging paragraph, so chapter boundaries read as transitions rather than as continuations.

---

## 7. Budget

### 7.1 Per call

Every component is bounded by a configuration value, so the budget is a formula and not a number.

| Component | Tokens |
|---|---|
| System prompt (page writer) | ≈ 800 |
| World rules | ≈ 120 |
| Character sheets | ≈ 110 × `context.max_characters_per_page` |
| Setting sheets | ≈ 110 × `context.max_settings_per_page` |
| Objective and hook | ≈ 30 |
| Chapter digests | ≈ `context.chapter_digest_max_words` × 1.35, times `organization.chapters − 1` |
| Recent summaries | ≈ 15 × `context.verbatim_summary_window` |
| Bridging paragraph | ≈ 60 |
| **Input, worst case (last page)** | **≈ 2 500 at the default configuration** |
| Output | `page.target_words × 1.35` ≈ 475 |

The worst case falls on the last page of the last chapter, where digests and summaries are both at maximum. **Measured on the first full run: 2 090 tokens on page 20**, so the bound holds with roughly 15% of headroom.

Version 2.1 budgeted ≈ 60 tokens per digest and put the worst case at ≈ 1 700. The run's digests came in at ≈ 270 each, four times that, and the whole of the overrun was that single line. The error was not arithmetic: nothing in either specification bounded digest length, so the phrase "one paragraph" was being asked to do the work of a constraint. `context.chapter_digest_max_words` now does it, set to the size the run actually needed rather than the size that had been assumed — the material in those long digests was read and used by the final chapter, so budgeting them down would have cost continuity.

**The worst case grows with `organization.chapters`, not with `organization.pages_total`.** That is the property worth defending: a longer story at the same chapter count costs no more per call.

### 7.2 Per run

At the default configuration: ≈ 40 000 input and ≈ 11 000 output tokens across the 47 calls of §12.2. Total tokens are comparable to v1.x; **peak tokens per call fall from ≈ 25 000 to ≈ 2 500**, and that is what removes the feasibility ceiling. No single model parameter can now make the design impossible. Input scales with `organization.pages_total` × the per-call figure above, so a configuration change is a cost change: doubling the page count doubles the bill.

**TR-13.** The system prompt and world rules are identical across every page call and shall be placed at the head of the payload so that a cacheable prefix is available. At ~920 tokens across ~20 calls this is the single largest saving available.

**TR-14.** Pages shall be generated sequentially. The bridging paragraph of TR-11 creates a real dependency on page N-1; parallelising within a chapter is possible only if `context.include_bridge_paragraph` is false, and that trade is not taken by default.

---

## 8. Validation

All mechanical checks run in code after each page call (FR-25).

| Check | Implementation | On failure |
|---|---|---|
| Length | Word count against `page.target_words ± page.length_tolerance` | Retry |
| Roster | Character names found in the page ⊆ names the **bible** declares | Retry |
| Non-empty | Page has prose and a final paragraph for the next bridge | Retry |
| Consistency | Separate call (TR-09), structured verdict | Retry |
| Beat coverage | On A6: pages 1…`pages_total` present, chapter *n* holds `derived.chapter_sizes[n]` pages | Block Phase B |
| Thread ledger | On C1: every `threads_opened` has a later `threads_closed` | Report |
| Flag ratio | On C3: flagged records ÷ `pages_total` ≤ `control.max_flagged_ratio` | Report |
| Anchor reversal | On A6: every page in `derived.anchor_pages` has an objective stating a change of direction | Redo A5 |
| Digest length | On chapter close: digest ≤ `context.chapter_digest_max_words` | Rewrite digest |
| Continuity | On chapter close: the chapter's facts against the fact ledger and prior digests | Repair (FR-40) |
| Config supersession | On load: every superseded value recorded | Report |

### 8.1 The consistency verdict

Agent 3 carries FR-12 to FR-14 and is the only check that rests on judgement, so its output is constrained to a fixed shape. The checks are enumerated, ordered and answered individually; there is no overall opinion field, because an overall opinion is what a model gives itself when it is not forced to look at particulars.

| # | Check | Question put to the agent |
|---|---|---|
| K1 | Appearance | Does the page contradict any appearance or costume in the loaded sheets? |
| K2 | Voice | Does any character speak against the traits in their sheet? |
| K3 | Arc | Does the page place a character beyond or behind their declared arc position? |
| K4 | World rules | Does anything in the page violate a world rule? |
| K5 | Objective | Does the page accomplish the objective of its beat entry? |
| K6 | Hook | Does the page end on its declared hook? |
| K7 | Off-stage mention | Does a character the beat does not declare act or speak, rather than merely being referred to? |

```json
{"page": 7, "verdict": "PASS",
 "checks": [
   {"id": "K1", "pass": true,  "evidence": "c1 scar on left hand, consistent with sheet"},
   {"id": "K4", "pass": false, "evidence": "lamp lit without fuel, contradicts r3"}
 ]}
```

**TR-14e.** K7 carries the half of FR-11 that code cannot decide. The roster check in §8 is deliberately permissive — any name the bible declares may appear — because a word matcher cannot tell a mention from an entrance. Restricting the matcher to the beat's own cast, as version 2.1 did, made the rule enforceable at the cost of forbidding a page to name an absent character at all: through the first run the protagonist's brother could only ever be "her brother", never "Tem", for nine pages. The constraint was real, unstated, and discovered by the checker rather than read from the requirement.

**TR-14b.** Every check shall carry an `evidence` string quoting or naming what in the page justifies the answer. A bare boolean is not auditable and cannot be reviewed by a person; requiring the agent to name the thing it looked at is the difference between a check and a rubber stamp.

**TR-14c.** `verdict` shall be `FAIL` if any check fails, computed by the orchestrator from the `checks` array rather than taken from the agent. The agent reports observations; the orchestrator draws the conclusion.

**TR-14d.** A response that does not parse against this shape counts as an endpoint failure, not a content failure, and is retried under FR-33. A malformed verdict is no evidence about the page.

**TR-15.** Retries shall reuse the assembled context byte-for-byte, with the failure reason appended. Reassembling invites a different failure.

**TR-16.** After `control.max_retries_per_page`, the page is accepted with `flagged: true` and its reason in the state record. The run never halts on a single page (FR-17).

**TR-16b.** Endpoint failures — timeouts, rate limits, transport errors, unparseable responses — shall be retried on a separate budget and shall never decrement `control.max_retries_per_page` (FR-33).

---

## 9. Resume

**TR-17.** On start-up with `control.resume_enabled`, the orchestrator shall determine the resume point as the lowest page number in `1…pages_total` with no file in `paths.pages_dir`, and rebuild summaries and character states by replaying `deltas.jsonl` up to that page.

**TR-18.** Resume shall be idempotent: a page file that exists is never regenerated, and a state record whose page already has a record is never appended twice. The state log is keyed by page number, and a replay that finds duplicates uses the last record and reports the anomaly.

**TR-19.** A resumed run shall verify that the configuration in `paths.runs_dir` matches the current `config.json`, and refuse to resume across a changed `organization` block or a changed derived shape. Comparing the derived values and not only the authoritative ones matters: two different `organization` blocks can derive the same shape, and should resume, while one edited value can change every chapter boundary. Half a story of one shape and half of another is worse than restarting.

---

## 10. Traceability

| FR | Mechanism | TR |
|---|---|---|
| FR-01 – FR-05 | Bible call; identifier scheme; beats.json schema | TR-04, TR-07 |
| FR-06 | A6 gate, including I-7 and beat coverage | TR-01 |
| FR-07 | `assemble(N)`, executed per call | TR-11, TR-12 |
| FR-08 | Sheet loading driven by `beat.characters` / `beat.settings`, capped separately | TR-10c, TR-11 |
| FR-09 | Only the bridging paragraph crosses from the previous page | TR-12 |
| FR-10, FR-11 | Length and roster checks in code, plus K7 for the judgement half of FR-11 | TR-14e, TR-15 |
| FR-12 – FR-14 | Separate consistency call with structured verdict | TR-09, TR-10 |
| FR-15 | Append to `deltas.jsonl` before the next page | TR-05 |
| FR-16 | `threads_opened` / `threads_closed` fields | TR-05 |
| FR-17 | Loop bound by `organization.pages_total`; flag-and-continue | TR-16 |
| FR-18 | Orchestrator rewrites remaining beat entries | TR-07 |
| FR-19 | Audit call over beat sheet and state log | TR-10 |
| FR-20 | Config interpolation into templates; no literals | TR-01, TR-03 |
| FR-21 | Invariants I-1 to I-8 | TR-01 |
| FR-22 | `chapter` field on every beat entry, sized by `derived.chapter_sizes` | TR-03b, TR-04 |
| FR-23 | Digest written at chapter close, length-checked, consumed by `assemble` | TR-12 |
| FR-24 | One file per page, atomic writes, resume point | TR-05, TR-17 |
| FR-25 | Section 8 checks, all in code | TR-15 |
| FR-26 | Run directory is write-only | TR-06 |
| FR-27 | `anchor` field on the beat entry; reversal check at the A6 gate | TR-07 |
| FR-28 | `chapter_title` on every beat entry | TR-04 |
| FR-29 | `manuscript.py`, rebuilt from `pages/` on every assembly | TR-05 |
| FR-30, FR-31 | `voice` in `assemble(N)` | TR-10b |
| FR-32 | Phase A stages the expansion first and commits it with the bible at A7 | TR-05 |
| FR-33 | Separate endpoint retry budget | TR-16b, TR-14d |
| FR-34 | Bible written only after the A6 gate passes | TR-05 |
| FR-35 | Thread ids minted at opening, in the same state record | TR-04b |
| FR-36 | `derive()` at load time, §3.1b | TR-03b |
| FR-37 | Superseded values reported at start-up and in the closing report | TR-03c |
| FR-38 | `facts` field on every state record | TR-04c |
| FR-39 | Continuity agent at chapter close, before the digest | TR-04c |
| FR-40 | `supersedes` field; repair runs through the ordinary page path | TR-04c, TR-18 |
| FR-41 | `recent` retained across digested chapters in `assemble(N)` | TR-11 |

Every FR is covered. FR-12 to FR-14 remain the weakest link: they are the only checks that still depend on a model's judgement, even though TR-09 moves that judgement out of the call that produced the text.

---

## 11. Open technical issues

| ID | Issue | Impact | Status |
|---|---|---|---|
| TI-01 | `model.id`, `model.max_output_tokens` and unit prices are null in the configuration | Cost per run unknown. No longer blocks feasibility, only estimation | Open |
| TI-02 | `model.temperature` 0.8 is proposed, not measured | Trades prose quality against instruction compliance | Open |
| TI-03 | `page.target_words` 350 proposed as the FR-10 reference | Now measured: six of the first run's seven retries were length failures, every one from above. 380 to 400 would have produced the same prose with no retries | Open, with evidence |
| TI-04 | `story.language` is `en`; the 1.35 tokens-per-word factor assumes English | A different language shifts section 7 | Open |
| TI-05 | Consistency check as a separate call (TR-09) not yet costed | Adds one call per page, roughly doubling call count. Mirrors OI-05 | Open |
| TI-06 | Behaviour when a premise cannot sustain `organization.pages_total` pages | Phase A has no rejection branch. Mirrors OI-04 | Open |
| TI-07 | Digest quality is unmeasured; a lossy digest is a silent failure | Compression loss remains the main risk the design introduces. `context.chapter_digest_max_words` now bounds the cost but not the quality, and the first run's evidence cuts the other way: its oversized digests carried material the final chapter used | Open |
| TI-08 | The manuscript assembler (12.3) has no governing requirement | The deliverable a reader actually wants is built by a component no FR mandates | **Closed in 2.1** — FR-29 |
| TI-10 | The A6 anchor check (FR-27) has no objective measure of what counts as a reversal | Implemented in the first run as a lexical test for reversal vocabulary, which would pass an objective that merely used the words. Mirrors OI-07 | **Open — blocking for any unattended run** |
| TI-11 | The schema of `facts` (FR-38) is undefined | An over-broad ledger costs tokens on every chapter-close audit; an over-narrow one misses the contradictions the audit exists to catch. Mirrors OI-08 | Open |
| TI-09 | Implementation language and runtime not fixed; section 12 assumes Python 3.11+ | File names in 12.3 are indicative until this closes | Open |

---

## 12. Build inventory

Everything that has to be **created in order to build the system**, as distinct from what the system produces when it runs (functional specification §3). This section is the contract for an implementer: a build that produces these artefacts, and no others, is complete.

### 12.1 Summary

| Kind | Count | Status |
|---|---|---|
| Configuration files | 1 | Exists |
| Prompt templates | 5 | To build |
| Orchestrator modules | 15 | To build |
| Test modules | 7 | To build |
| Agents (model call types) | 5 | To build, as templates + wrapper |
| Skills, plugins, external services | **0** | See 12.6 |

Language and runtime are assumed to be Python 3.11 or later (TI-09). File names below are indicative; responsibilities and boundaries are not.

### 12.2 Agents

Four call types. Each is a system prompt plus an input contract, not a persistent process. Whether they are realised as plain API calls or as declared agent definitions is an implementation choice; the contracts are identical either way.

| # | Agent | Temperature | Input | Output | Template | Implements |
|---|---|---|---|---|---|---|
| 1 | Bible | `model.temperature` | Premise, `story`, `organization`, `bible` bounds | Premise expansion, rules, sheets, beat sheet with chapter titles and anchor reversals | `prompts/bible.md` | FR-01 to FR-05, FR-27, FR-28, FR-32 |
| 2 | Page | `model.temperature` | Assembled context (§6), tone and language included | Prose of one page, nothing else | `prompts/page.md` | FR-10, FR-14, FR-30, FR-31 |
| 3 | Consistency | 0 | The finished page, its sheets, the rules, its objective | The verdict shape of §8.1 | `prompts/consistency.md` | FR-12 to FR-14, TR-09 |
| 4 | Continuity | 0 | The closing chapter's pages, the fact ledger, prior digests | Contradictions, each naming the page at fault | `prompts/continuity.md` | FR-39 |
| 5 | Audit | 0 | Beat sheet, state log, declared arcs | Report content | `prompts/audit.md` | FR-19 |

**Call volume at the default configuration:** 1 + 20 + 20 + 5 + 1 = **47 calls minimum**, plus one Page call and one Consistency call per retry, and one Page call per continuity repair. Agent 3 is what doubles the count, and is the subject of TI-05. Agent 4 costs one call per chapter, so it scales with `organization.chapters` rather than with the page count.

Agents 2 and 3 must never be merged into one call. That separation is the mechanism that retires the principal risk of version 1.x (TR-09).

### 12.3 Orchestrator modules

| Module | Responsibility | Implements | Depends on |
|---|---|---|---|
| `run.py` | Entry point. Arguments, run directory, phase sequencing | — | all |
| `config_loader.py` | Parse `config.json`, invariants I-1 to I-6 and I-8, copy into run dir | FR-20, FR-21, TR-01, TR-02 | derive |
| `derive.py` | Chapter sizes, act spans, anchor pages, supersession report | FR-36, FR-37, TR-03b, TR-03c | — |
| `schemas.py` | Shapes of the beat entry, the state record and the config | TR-04 | — |
| `agents.py` | Model call wrapper: template rendering, temperature per call type, retry on transport error | TR-07, TR-08, TR-10 | config_loader |
| `phase_a.py` | Bible call, A6 gate, invariant I-7, write bible to disk | FR-01 to FR-06 | agents, schemas |
| `context.py` | `assemble(N)`: selective loading, digests, recent summaries, bridge | FR-07 to FR-09, FR-26, TR-11, TR-12 | state, digest |
| `phase_b.py` | Page loop, retry budget, flagging, page file writes | FR-15, FR-17, FR-22, TR-15, TR-16 | context, agents, validators |
| `validators.py` | Length and roster checks, in code. No model involvement | FR-10, FR-11, FR-25 | schemas |
| `consistency.py` | Agent 3 invocation and verdict parsing | FR-12 to FR-14, TR-09 | agents |
| `state.py` | Append to `deltas.jsonl`, replay, thread ledger, atomic writes | FR-15, FR-16, TR-05 | schemas |
| `digest.py` | Build and write the chapter digest at each chapter close, within its word bound | FR-23 | state |
| `continuity.py` | Chapter-close audit against the fact ledger; repair budget and superseding records | FR-38 to FR-40 | state, agents |
| `resume.py` | Resume point, idempotency, refusal across a changed `organization` | FR-24, TR-17 to TR-19 | state, config_loader |
| `phase_c.py` | Thread and arc audit, chapter balance, flag ratio, Agent 4 | FR-19 | state, agents |
| `manuscript.py` | Join page files in order into `paths.manuscript`, under chapter titles | FR-29 | schemas |

### 12.4 Prompt templates

Held as files, not as strings in code, so that a prompt change is reviewable as a diff. Every configuration value reaches them by interpolation; none is written literally (FR-20).

| File | For | Must state |
|---|---|---|
| `prompts/bible.md` | Agent 1 | Output formats of §4, identifier scheme, act split and chapter grouping |
| `prompts/page.md` | Agent 2 | Prose only, honour objective and hook, target length, no structural markup |
| `prompts/consistency.md` | Agent 3 | Checks K1 to K6 of §8.1 and the response shape, each answered with its evidence |
| `prompts/continuity.md` | Agent 4 | What counts as a contradiction of fact, and the requirement to name the page at fault |
| `prompts/audit.md` | Agent 5 | Report shape, what counts as an unclosed thread or an incomplete arc |

### 12.5 Tests

The build is not complete without these, because three requirements are only meaningful as executable checks.

| File | Covers |
|---|---|
| `tests/test_config_invariants.py` | I-1 to I-6 and I-8, including the abort path (FR-21) |
| `tests/test_derivation.py` | FR-36: chapter sizes, act spans and anchors at several configurations, including ones that do not divide evenly; FR-37 supersession reporting |
| `tests/test_continuity.py` | FR-39 and FR-40: a planted contradiction is found at chapter close, repaired once, and the replay prefers the superseding record |
| `tests/test_context_assembly.py` | FR-08 and FR-09: only declared sheets, no prior page text beyond the bridge |
| `tests/test_validators.py` | FR-10 and FR-11 against fixture pages that pass and fail each band |
| `tests/test_resume.py` | FR-24: idempotency, and refusal to resume across a changed `organization` |
| `tests/fixtures/` | A miniature bible and three page fixtures, sized for a 4-page configuration |

**The acceptance test for FR-20 and FR-36** is not a unit test: change *one value* in `organization`, re-run, and confirm a story of the new shape with no other edit to the configuration, to code or to templates. Version 2.1 would have failed this test on every one of its five organization values.

### 12.6 Explicitly not built

Listed so that an implementer does not invent them:

- **No skills and no plugins.** The system is an orchestrator and four prompts.
- **No database.** State is files (functional specification §4).
- **No external services** beyond the model endpoint.
- **No user interface and no authentication.** The entry point is a command line.
- **No streaming or live monitoring.** Version 1.x needed it to catch drift; the orchestrator now catches drift by measurement.

### 12.7 Build order

Dependency order, so that each stage is testable before the next exists:

```
config_loader + schemas   →   state + digest   →   context
        ↓                                              ↓
     agents          →      validators + consistency   ↓
        ↓                          ↓                   ↓
     phase_a          →          phase_b          →  phase_c
                                    ↓
                        resume · manuscript · run
```

A vertical slice — `config_loader`, `agents`, `phase_a` — is runnable on its own and produces a complete bible, which is the first point at which the design can be judged against real output.
