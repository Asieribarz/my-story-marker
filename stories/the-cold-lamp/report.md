# Closing report

| | |
|---|---|
| **Run** | `runs/2026-09-15T17-36` |
| **Configuration** | `config.json` v2.0 (copied into the run directory at start-up, TR-02) |
| **Specifications** | Functional v2.1, Technical v2.1 |
| **Premise (run argument)** | A young sailor who fears deep water crosses a storm-blown archipelago to find her brother, missing since the lighthouse went dark. |
| **Deliverable** | `story.md` — *The Cold Lamp*, 20 pages, 7 843 words of prose |
| **Verdict** | Accepted, with deviations recorded in section 6 |

---

## 1. Acceptance criteria (functional specification §9)

| # | Criterion | Result |
|---|---|---|
| 1 | `pages_total` pages, in `chapters` chapters, honouring `acts` | **PASS** — 20 pages, 5 chapters of 4, setup 4 / development 12 / resolution 4 |
| 2 | No character changes name, appearance or voice without justification | **PASS** — one violation caught at the gate and corrected before the page was written (§4) |
| 3 | Every setting described on its first appearance | **PASS** — all five sheets carry appearance and atmosphere; A6 checked it |
| 4 | No open threads, no incomplete arcs | **PASS** — 8 of 8 threads closed, 6 of 6 arcs reach their declared final state |
| 5 | Flagged pages ≤ `control.max_flagged_ratio` | **PASS** — 0 of 20 flagged (ceiling 10%) |
| 6 | No causal gaps; chapter boundaries fall sensibly | **PASS, qualified** — one continuity defect was found mid-run and corrected; see D8 |
| 7 | Each anchor page turns the story | **PASS, qualified** — pages 5, 10 and 16 turn it; the gate that checked this is a lexical proxy, see D10 |
| 8 | `paths.manuscript` exists, in `story.language`, every page in order under its chapter title | **PASS** — `story.md`, English, five titled chapters |
| 9 | Re-running with a changed `organization` block produces a story of the new shape | **NOT TESTED** — this run exercised one configuration only |

---

## 2. Thread ledger (C1 — FR-16, FR-19)

Threads are minted when they open (FR-35, TR-04b); the ledger below is the replay of `state/deltas.jsonl`.

| Thread | What it promised | Opened | Closed |
|---|---|---|---|
| t1 | The name written over her brother's on the keepers' roll | p2 | p13 |
| t2 | Halloran's note of hand, held by the warden | p4 | p17 |
| t5 | The small wet prints going up the tower stair | p6 | p10 |
| t3 | The reservoir dry to the brass, and eleven casks missing | p7 | p11 |
| t4 | A three-stroke bell rung eight days early | p8 | p13 |
| t6 | Whose side Mara stands on, and who will keep the light | p10 | p19 |
| t8 | Why her brother put the light out | p10 | p18 |
| t7 | The nine-day claim on the keeper's oil | p11 | p19 |

**Unclosed threads: none. Closes without a matching open: none.**

---

## 3. Character arcs (C2 — FR-02)

Each arc is checked against the final state declared in Phase A, using the last state record that mentions the character.

| Id | Character | Declared arc | Last state in the log | Reached |
|---|---|---|---|---|
| c1 | Mara Vell | fearful → resolute | p20: relief keeper on Calder Rock, standing the watch over the deepest ground in the archipelago | Yes |
| c2 | Tem Vell | hidden → accountable | p18: signed, and giving the article eleven direction and what followed it to the roll | Yes |
| c3 | Halloran Keeve | evasive → true | p17: free of the note, papers back in his own hand, and telling it straight | Yes |
| c4 | Ester Quill | unchallenged → exposed | p20: held under her own article, with article eleven to follow | Yes |
| c5 | Dov Ashe | obedient → refusing | p13: broke with the warden — "when she asks me I will have counted wrong" | Yes |
| c6 | Nell Carrow | silent → sworn | p19: sworn keeper of the Cold Lamp, showing three flashes to the minute | Yes |

**Incomplete arcs: none.** c5 completes earliest, on page 13, and does not appear again; his beat count (2) is the minimum the A6 gate allows.

---

## 4. Balance, length and flags (C3)

**Length (FR-10).** Band 280–420 words at `page.target_words` 350 ± 20%. All 20 pages in band; 0 out of band. Mean 392, which sits high in the band — every page was written long and trimmed rather than padded.

| Chapter | Title | Pages | Words |
|---|---|---|---|
| 1 | The Dark on the Water | 1–4 | 1 578 |
| 2 | The Cold Lamp | 5–8 | 1 450 |
| 3 | Wreck Law | 9–12 | 1 503 |
| 4 | The Drowned Stair | 13–16 | 1 667 |
| 5 | Slack Water | 17–20 | 1 645 |

Spread between the longest and shortest chapter is 217 words, 14% of the mean. **No chapter imbalance to report.**

**Acts.** setup 1 578 / development 4 620 / resolution 1 645 words, against a page split of 4 / 12 / 4. Proportional.

**Flagged pages (FR-19): none.** `control.max_flagged_ratio` was never approached.

**Retries (`control.max_retries_per_page` = 2).** 7 content retries across 5 pages; no page exhausted its budget.

| Page | Retries | Rejected by | Reason |
|---|---|---|---|
| 2 | 2 | K1 appearance, K6 hook, then FR-10 length | Halloran took his cap off, which his sheet forbids; the hook landed two paragraphs early; the rewrite ran to 434 words |
| 13 | 1 | FR-10 length | 431 words |
| 15 | 1 | FR-10 length | 421 words |
| 16 | 2 | Final-paragraph check, then FR-10 length | The closing line was six words, too short to serve as the next page's bridge; the fix ran to 423 words |
| 17 | 1 | FR-10 length | 421 words |

Six of the seven retries were length. **FR-10 is the binding constraint of this configuration**, and it binds from above: the natural length of a scene at this tone sits just over the ceiling.

**Endpoint failures (FR-33): none.** The separate budget required by TR-16b was never drawn on.

---

## 5. Context budget, measured against §7 of the technical specification

The assembled context was measured at four points, converted at the specification's own 1.35 tokens per word.

| Page | Words | ≈ Tokens | Note |
|---|---|---|---|
| 1 | 480 | 650 | No digests, no summaries, no bridge |
| 5 | 723 | 975 | One digest, no bridge (chapter opening, TR-12) |
| 12 | 1 024 | 1 380 | Two digests, three summaries, bridge |
| 20 | 1 549 | **2 090** | Four digests, three summaries, bridge — the worst case |

The specification budgets **≈1 700 input tokens** for the worst case. The measured worst case is **≈2 090, some 23% over**, and the whole of the overage is the digests: §7.1 budgets ≈60 tokens per chapter digest, and the five digests written here run 161–237 words, ≈220–320 tokens each. See D4.

The design property that matters still holds: the per-call payload is bounded and grows only with the number of chapters. Peak tokens per call are nowhere near the ≈25 000 that made version 1.x infeasible.

---

## 6. Deviations from the specification

Recorded here rather than silently absorbed, because several of them are defects in the specifications rather than in the run.

**D1 — The system in §12 was not built; the run was orchestrated by hand.**
`config.json` sets `model.id` to `null` (TI-01), and none of the 13 orchestrator modules, 4 prompt templates or 5 test modules of §12 exist in the branch. The flow was executed directly: the deterministic parts of the specification — the invariants I-1 to I-5, the A6 gate, FR-10 and FR-11 validation, `assemble(N)`, the thread and arc replay, chapter balance and manuscript assembly — were written as code and actually run, so every mechanical claim in this report is a measurement. The narrative judgements were not made by a separate process. See D2.

**D2 — TR-09 is satisfied in form, not in substance.**
The consistency verdicts (K1–K6, one per page, with evidence per check as TR-14b requires) were produced in a pass separate from the writing pass, over the finished page text, and the `verdict` field was computed by the orchestrator from the `checks` array and never taken from the judge (TR-14c). But the judge was not an independent endpoint. This is exactly the weakness §10 of the technical specification names as the weakest link, and OI-05 and TI-05 remain open for the right reason. The K1 failure on page 2 shows the check is not a rubber stamp; it does not show it is independent.

**D3 — FR-32 and FR-34 contradict each other.**
FR-32 requires the premise expansion to be persisted to `paths.premise` *before* the world rules are generated. FR-34 requires that nothing be written to the bible until A6 passes. Both cannot hold literally. Resolved here by staging the whole bible in write order and committing it atomically at A7, which honours FR-34's intent and FR-32's ordering. One of the two requirements should be reworded.

**D4 — Chapter digests exceed their budget by roughly four times.**
§7.1 allows ≈60 tokens per digest; the five written here average ≈270. Nothing in the specification bounds digest length — FR-23 requires "one paragraph" and no more. This is the sole cause of the overage in section 5, and it is the mechanism TI-07 worries about from the other side: shorter digests would have met the budget and lost material that pages 17–20 depended on.

**D5 — `context.verbatim_summary_window` is inert at this configuration.**
FR-23 removes a digested chapter's individual summaries from later contexts, and `pages_per_chapter` is 4, so the window can never contain more than 3 summaries however large it is set. The configured value of 8 has no effect on any page of this run. Either the window should be documented as a ceiling that only binds when chapters are longer than it, or FR-23 and FR-15 should be reconciled.

**D6 — `context.max_sheets_per_page` = 3 caps every scene at two named characters.**
`assemble(N)` counts character sheets and setting sheets against one budget. Every page that declares a setting therefore has room for two characters and no more. The whole story is written in two-handers as a direct consequence. This is a legitimate design outcome, not a fault, but the specification nowhere says that the sheet budget is also a cast-per-scene budget, and an author reading §6 would not expect it.

**D7 — FR-11, implemented as TR-04 specifies, forbids naming absent characters.**
The roster check is "character ids and names found in the page ⊆ ids the beat declares". Applied literally, a page may not so much as mention an undeclared character by name. Pages 1 to 9 therefore say "her brother" and never "Tem", and pages 4, 11 and 13 say "the warden" and never "Quill". The prose absorbs this well — arguably better than the alternative — but it is a strong constraint that neither specification states, and it was discovered by the checker rather than read off the requirement. The implementation here resolves shared surnames by mapping each token to the set of characters that own it ("Vell" passes on any page where either sibling is declared).

**D8 — A continuity defect was found after the affected pages had been committed, and the specified flow has no branch for it.**
Writing page 11 exposed an inconsistent calendar across pages 3, 8, 9 and 11: dates of the month and days of the storm season had been used interchangeably, and r5 puts the season at nine days. FR-18 covers deviations from the *beat sheet*, not continuity errors in *already-written pages*, and neither specification says what to do. Handled by fixing the four pages, re-issuing 3 and 8 through the normal commit path, and letting TR-18's "a replay that finds duplicates uses the last record and reports the anomaly" absorb the consequence.

> **TR-18 anomaly, reported as required: `state/deltas.jsonl` holds duplicate records for pages 3 and 8. The replay used the last record of each.**

The underlying gap is real: per-page validation cannot catch a contradiction between page 3 and page 11, because it never sees both. The two-level compression (FR-23) makes it likelier, not less likely, since page 11 saw chapter 1 only as a digest. A cross-page continuity audit at each chapter close, or a fact ledger carried in the state log, would close it. Recommend a new functional requirement.

**D9 — Diagnostic traces (FR-26) were written for all 20 pages, 15 of them after the fact.**
`assemble(N)` is a pure function of the bible and of state up to page N, so the regenerated traces are byte-identical to what was used at write time; their timestamps are not. No trace was ever read back as state (TR-06).

**D10 — The A6 anchor check is a lexical proxy, exactly as OI-07 predicts.**
Pages 5, 10 and 16 were accepted as reversals by a regular expression looking for reversal markers in the objective ("turns into", "stops being", "cannot reverse", "no longer", "instead of"). All three passed, and all three do in fact turn the story. The check would equally pass an objective that merely used the vocabulary. **OI-07 and TI-10 should be treated as blocking for any unattended run**, because this is the one gate whose failure mode is silent.

---

## 7. Open issues touched by this run

| ID | Status after the run |
|---|---|
| OI-02 / TI-03 | `page.target_words` 350 is workable but tight: 6 of 7 retries were length, all from above. A target of 380–400 would have produced the same prose with no retries. |
| OI-04 / TI-06 | Not exercised. The premise sustained 20 pages comfortably; the rejection branch remains unwritten and untested. |
| OI-05 / TI-05 | Still open, and now costed in principle: 20 consistency checks against 20 page calls, doubling the call count exactly as §12.2 predicts. |
| OI-07 / TI-10 | Still open. See D10. |
| TI-01 | Still open. `model.id` and `model.max_output_tokens` are null, which is why §12 could not be run as built software. |
| TI-04 | Not exercised; the run was in `en`, where the 1.35 factor holds. |
| TI-07 | Now has one data point on the other side: the digests that carried this story were four times the budgeted size, and the material they carried was used. |
| TI-09 | Unchanged; the code written for this run is Python 3.12 and lives outside the repository. |

---

## 8. Inventory produced

```
bible/premise.md, rules.md, characters/ (6), settings/ (5), beats.json
state/deltas.jsonl          22 records for 20 pages (2 duplicates, D8)
state/chapters/01..05.md    5 digests
pages/01..20.md             20 pages, frontmatter added by the orchestrator (TR-08)
runs/2026-09-15T17-36/      config.json, ctx-01..20.md, verdict-01..20.json
story.md                    the manuscript, rebuilt from pages/ (FR-29)
report.md                   this file
```
