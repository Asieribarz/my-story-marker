# Technical specification
## Adventure story generator agent — file-backed orchestration

| | |
|---|---|
| **Version** | 2.0 |
| **Date** | 15 September 2026 |
| **Implements** | Functional specification v2.0 |
| **Configuration** | `story-config.json` |
| **Status** | Draft for review |

---

## 1. Scope

The functional specification defines *what* the system produces. This document defines *how*: file layout and formats, the configuration contract, the per-call prompt contracts, context assembly, token and cost budget, validation code and resume.

Each technical requirement (TR-xx) traces to a functional requirement (FR-xx) in section 10.

### 1.1 Change from version 1.x

Version 1.x specified a single-prompt harness in which the transcript was the memory. Its blocking defect was arithmetic: a complete run needed ≈25 000 output tokens **in one response**, so feasibility depended entirely on a single model parameter, and no amount of prompt engineering could move it. Two further properties made it hard to operate — a run could not be resumed, and mechanical validation was the model's report on its own work rather than a measurement.

Moving state to disk retires all three. The cost is an orchestrator that can itself be wrong, and page-to-page continuity that must now be engineered rather than assumed.

---

## 2. Architecture

```
story-config.json          ← single source of control and organization values
    │
    ▼
orchestrator ──► model call (Phase A: bible)      ──► bible/*
             ──► model call (Phase B: page N) ×P  ──► pages/NN.md
             ──► deterministic validation (code)   ──► state/deltas.jsonl
             ──► model call (Phase C: report)      ──► report.md
```

The orchestrator owns the loop, the counters, retry, the stop condition and every file write. The model owns prose and narrative judgement, and nothing else.

**TR-01.** The orchestrator shall read every control and organization value from `story-config.json` at start-up. No such value shall appear as a literal in code or in a prompt template; prompts receive them by interpolation (FR-20).

**TR-02.** The configuration in force shall be copied into the run directory at start-up, so that a completed run carries the parameters that produced it.

---

## 3. Configuration contract

### 3.1 Validation

Checked before the first model call. Failure aborts when `control.abort_on_invalid_config` (FR-21).

| # | Invariant | Failure mode it prevents |
|---|---|---|
| I-1 | `chapters × pages_per_chapter = pages_total` | Chapters that do not tile the story |
| I-2 | `sum(acts) = pages_total` | Act split that does not cover every page |
| I-3 | `anchor_pages ⊆ [1, pages_total]` | Anchor beyond the last page |
| I-4 | `world_rules_min ≤ world_rules_max` | Unsatisfiable bible bounds |
| I-5 | `0 < page.length_tolerance < 1` | Length check that can never fail, or never pass |
| I-6 | every path in `paths` is writable | Failure discovered after tokens are spent |
| I-7 | `context.max_sheets_per_page ≥ max sheets any beat declares` | Context silently truncating a declared character |

I-7 is checked after the beat sheet exists, at the A6 gate, not at start-up.

### 3.2 Binding

Both specifications reference configuration by path. The orchestrator exposes the parsed config to prompt templates under the same names, so `{{organization.pages_total}}` in a template and `organization.pages_total` in the specification denote one value with one definition.

**TR-03.** Changing the shape of a story shall require editing `story-config.json` only. A change to `organization` that leaves prompts and code untouched is the acceptance test for FR-20, and is listed as an acceptance criterion in §9 of the functional specification.

---

## 4. File layout and formats

```
story-config.json
bible/
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
{"page": 7, "chapter": 2, "act": "development", "anchor": false,
 "objective": "Mara reaches the lighthouse and finds it abandoned",
 "hook": "the lamp is cold", "characters": ["c1", "c3"], "settings": ["s2"]}
```

```json
{"page":7,"chapter":2,"words":312,"retries":0,"flagged":false,
 "summary":"Mara reaches the lighthouse; it is abandoned and the lamp is cold.",
 "states":{"c1":"at the lighthouse, shaken"},
 "threads_opened":["t4"],"threads_closed":["t2"]}
```

**TR-04.** Identifiers (`c1`, `s2`, `t4`) shall be assigned in Phase A and are immutable; every later reference uses the identifier. This makes an FR-11 violation decidable by set membership rather than by matching names that legitimately vary in prose.

**TR-05.** Every write shall be atomic — written to a temporary file and renamed — so that an interrupted run never leaves a half-written page or state record (FR-24).

**TR-06.** The run directory shall be write-only from the orchestrator's perspective: nothing under `paths.runs_dir` is ever read back as state (FR-26).

---

## 5. Per-call contracts

Three call types, each with its own system prompt.

| Call | Input | Output | Frequency |
|---|---|---|---|
| Bible | Premise, `story`, `organization`, `bible` bounds | Rules, characters, settings, beat sheet | Once |
| Page | Assembled context (section 6) | Prose of one page | `pages_total`, plus retries |
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
    beat    ← beats[N]
    rules   ← read(paths.world_rules)
    sheets  ← [read(s) for s in beat.characters + beat.settings]
    assert len(sheets) ≤ context.max_sheets_per_page
    digests ← [read(chapters/c) for c in closed chapters before beat.chapter]
    recent  ← summaries of the last context.verbatim_summary_window pages
    bridge  ← final paragraph of pages/(N-1).md   if context.include_bridge_paragraph
    return render(rules, sheets, beat.objective, beat.hook, digests, recent, bridge)
```

**TR-11.** Character states in the context shall come from the **last** record in `deltas.jsonl` that mentions each character, not from the sheet, whose `state` is the Phase A value. The sheet holds what is immutable; the log holds what has happened.

**TR-12.** A page whose beat opens a chapter shall receive the previous chapter's digest in place of a bridging paragraph, so chapter boundaries read as transitions rather than as continuations.

---

## 7. Budget

### 7.1 Per call

| Component | Tokens |
|---|---|
| System prompt (page writer) | ≈ 800 |
| World rules | ≈ 120 |
| Sheets, up to `context.max_sheets_per_page` | ≈ 110 each |
| Objective and hook | ≈ 30 |
| Chapter digests, closed chapters | ≈ 60 each |
| Recent summaries, within the window | ≈ 15 each |
| Bridging paragraph | ≈ 60 |
| **Input, worst case (last page)** | **≈ 1 700** |
| Output | `page.target_words × 1.35` ≈ 475 |

The worst case falls on the last page of the last chapter, where digests and summaries are both at maximum. It is bounded and roughly constant, which is the whole point of the design.

### 7.2 Per run

At the default configuration: ≈ 34 000 input and ≈ 11 000 output tokens across ≈ 22 calls. Total tokens are comparable to v1.x; **peak tokens per call fall from ≈25 000 to ≈2 200**, and that is what removes the feasibility ceiling. No single model parameter can now make the design impossible.

**TR-13.** The system prompt and world rules are identical across every page call and shall be placed at the head of the payload so that a cacheable prefix is available. At ~920 tokens across ~20 calls this is the single largest saving available.

**TR-14.** Pages shall be generated sequentially. The bridging paragraph of TR-11 creates a real dependency on page N-1; parallelising within a chapter is possible only if `context.include_bridge_paragraph` is false, and that trade is not taken by default.

---

## 8. Validation

All mechanical checks run in code after each page call (FR-25).

| Check | Implementation | On failure |
|---|---|---|
| Length | Word count against `page.target_words ± page.length_tolerance` | Retry |
| Roster | Character ids and names found in the page ⊆ ids in `beat.characters` | Retry |
| Non-empty | Page has prose and a final paragraph for the next bridge | Retry |
| Consistency | Separate call (TR-09), structured verdict | Retry |
| Beat coverage | On A6: pages 1…`pages_total` present, each chapter holds `pages_per_chapter` | Block Phase B |
| Thread ledger | On C1: every `threads_opened` has a later `threads_closed` | Report |
| Flag ratio | On C3: flagged records ÷ `pages_total` ≤ `control.max_flagged_ratio` | Report |

**TR-15.** Retries shall reuse the assembled context byte-for-byte, with the failure reason appended. Reassembling invites a different failure.

**TR-16.** After `control.max_retries_per_page`, the page is accepted with `flagged: true` and its reason in the state record. The run never halts on a single page (FR-17).

---

## 9. Resume

**TR-17.** On start-up with `control.resume_enabled`, the orchestrator shall determine the resume point as the lowest page number in `1…pages_total` with no file in `paths.pages_dir`, and rebuild summaries and character states by replaying `deltas.jsonl` up to that page.

**TR-18.** Resume shall be idempotent: a page file that exists is never regenerated, and a state record whose page already has a record is never appended twice. The state log is keyed by page number, and a replay that finds duplicates uses the last record and reports the anomaly.

**TR-19.** A resumed run shall verify that the configuration in `paths.runs_dir` matches the current `story-config.json`, and refuse to resume across a changed `organization` block. Half a story of one shape and half of another is worse than restarting.

---

## 10. Traceability

| FR | Mechanism | TR |
|---|---|---|
| FR-01 – FR-05 | Bible call; identifier scheme; beats.json schema | TR-04, TR-07 |
| FR-06 | A6 gate, including I-7 and beat coverage | TR-01 |
| FR-07 | `assemble(N)`, executed per call | TR-11, TR-12 |
| FR-08 | Sheet loading driven by `beat.characters` / `beat.settings`, capped | TR-11 |
| FR-09 | Only the bridging paragraph crosses from the previous page | TR-12 |
| FR-10, FR-11 | Length and roster checks in code | TR-15 |
| FR-12 – FR-14 | Separate consistency call with structured verdict | TR-09, TR-10 |
| FR-15 | Append to `deltas.jsonl` before the next page | TR-05 |
| FR-16 | `threads_opened` / `threads_closed` fields | TR-05 |
| FR-17 | Loop bound by `organization.pages_total`; flag-and-continue | TR-16 |
| FR-18 | Orchestrator rewrites remaining beat entries | TR-07 |
| FR-19 | Audit call over beat sheet and state log | TR-10 |
| FR-20 | Config interpolation into templates; no literals | TR-01, TR-03 |
| FR-21 | Invariants I-1 to I-7 | TR-01 |
| FR-22 | `chapter` field on every beat entry | TR-04 |
| FR-23 | Digest written at chapter close, consumed by `assemble` | TR-12 |
| FR-24 | One file per page, atomic writes, resume point | TR-05, TR-17 |
| FR-25 | Section 8 checks, all in code | TR-15 |
| FR-26 | Run directory is write-only | TR-06 |

Every FR is covered. FR-12 to FR-14 remain the weakest link: they are the only checks that still depend on a model's judgement, even though TR-09 moves that judgement out of the call that produced the text.

---

## 11. Open technical issues

| ID | Issue | Impact | Status |
|---|---|---|---|
| TI-01 | `model.id`, `model.max_output_tokens` and unit prices are null in the configuration | Cost per run unknown. No longer blocks feasibility, only estimation | Open |
| TI-02 | `model.temperature` 0.8 is proposed, not measured | Trades prose quality against instruction compliance | Open |
| TI-03 | `page.target_words` 350 proposed as the FR-10 reference | Sets the length band for every run | Open, proposed |
| TI-04 | `story.language` is `en`; the 1.35 tokens-per-word factor assumes English | A different language shifts section 7 | Open |
| TI-05 | Consistency check as a separate call (TR-09) not yet costed | Adds one call per page, roughly doubling call count. Mirrors OI-05 | Open |
| TI-06 | Behaviour when a premise cannot sustain `organization.pages_total` pages | Phase A has no rejection branch. Mirrors OI-04 | Open |
| TI-07 | Digest quality is unmeasured; a lossy digest is a silent failure | Compression loss is the main risk the new design introduces | Open |
