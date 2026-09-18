# Closing Audit Report: The Glass Ferry

**Run date:** 2026-09-18
**Story:** the-glass-ferry
**Phase:** C (Closing)
**Report written by:** Closing Auditor (Agent 5)

---

## 1. What was produced

The run produced a complete story of **6 pages**, grouped into **2 chapters of 3 pages each**, totalling **2383 words**. The structure matches the derived shape exactly:

- **Chapter 1 ("The Passenger"):** pages 1–3, 1194 words
- **Chapter 2 ("The Cost"):** pages 4–6, 1189 words
- **Act structure:** Setup (page 1, 1 page); Development (pages 2–5, 4 pages); Resolution (page 6, 1 page)
- **Word distribution:** Per-page range 1063–1194 words across two chapters, with no individual page counts recorded in the audit data. Target was 380 words per page within a band of 304–456 words.

The shape conforms to `derived.chapter_sizes` [3, 3], `derived.act_spans` {setup: [1,1], development: [2,5], resolution: [6,6]}, and anchor pages at positions [2, 3, 5] as derived from `organization.pages_total: 6`, `organization.chapters: 2`, and `organization.act_proportions: {setup: 0.2, development: 0.6, resolution: 0.2}`.

The manuscript `stories/the-glass-ferry/story.md` exists, is written in English, and contains every page in order under its chapter titles (FR-29).

---

## 2. Open threads

Of the five identified open threads, status is as follows:

**Closed threads:**
- **t4:** "Whether Vex's bound wound holds the three hours to the sanctuary" — closed. The story shows Vex reaching the far shore with the documents, having maintained the binding through the crossing, and finding the sanctuary referenced in the objective (page 6: "the documents held against the bound wound, gone up the narrow path into the mist").
- **t5:** "What the bundle of documents contains and why it is going to the far shore" — closed. The story resolves the *why* (Paine's payment, the sanctuary on the far shore) and the *destination*, though not the *contents*. The contents remain deliberately mysterious, which is consistent with Vex's characterization as hunted and defensive.
- **t6, t7, t8, t9:** Opened later in the story and all closed on page 6 as specified.

**Open threads — DEFECT:**
- **t1, t2, t3:** Opened on page 1 "around Paine's commission." These threads are not explicitly named in the audit payload, making their content inferential from context. Based on page 1's objective ("receives hidden instructions to prevent the passenger from reaching the far shore"), they concern: (a) whether Kael will accept Paine's money and commission; (b) what Paine's intentions are and what will happen if Kael refuses; (c) the nature and purpose of the passenger's mission.

The story resolves (a): Kael accepts the money on page 1, then consciously reverses that decision on page 3 ("Then forward," he said). However, (b) and (c) remain unresolved. Paine does not reappear after page 1; the reader never learns what he does when Kael fails to deliver. The bundle's contents are never disclosed. The "men waiting on the quay" mentioned by Vex are named as a threat but never shown acting or failing to act. These are narrative promises (opening a thread means inviting the reader to expect a payoff) that the story did not keep.

**Finding:** Three open threads constitute a defect against the acceptance criterion "The closing report reports no open threads." The mandate to report whether an open thread is "a promise the story made and did not keep" or "an ending that stays open on purpose" applies here: t1-t3 were opened by premises (Paine's stated plan, the unexplained documents, the threat at the dock) and closed by narrative necessity rather than by answering the questions they posed. This is a defect in the run, not in the specification.

---

## 3. Incomplete character arcs

**Merchant Paine (c3) — INCOMPLETE:**

| Aspect | Declared | Actual |
|---|---|---|
| Initial state | "Believes he controls everyone" | Shown controlling the room, the situation, Kael (briefly) |
| Final state | "Discovers he cannot control what matters most" | Still in his harbor-window office, hands folded, having got the agreement he arranged the room to get |
| Last appearance | (implicit in beat sheet) | Page 1 only |
| Recorded state in log | Not provided in audit | "Still in his harbor-window office, hands folded, having got the agreement he arranged the room to get" |

Paine's arc is incomplete. He is declared to *discover* he cannot control what matters most, but the story does not show this discovery. He appears on page 1 only, secures Kael's agreement, and is never tested against the outcome (Kael's failure to deliver, the ferry's loss, Vex's escape). The story does not stage the moment in which he learns that his control is illusory. This constitutes an unfulfilled arc.

**Other characters:**
- **Kael (c1):** Complete. Arc from "confident in his own integrity" to "willing to sacrifice everything for integrity" is demonstrated by his choice to deliver Vex despite the payment, and the ferry's loss as the price of that choice (pages 3, 5, 6).
- **Vex (c2):** Complete. Arc from "hunted and desperate, trusting no one" to "willing to trust an unexpected ally" is shown by accepting Kael's commitment on page 3 and working with him and Orin through pages 4–6, escaping with the documents.
- **Orin (c4):** Complete. Arc from "naive about moral complexity" to "aware that integrity demands sacrifice" is shown by his silent acceptance of the ferry's loss on page 6 ("Orin set the bucket down without being told").

**Finding:** One of four character arcs (25%) is incomplete. This is a defect against the acceptance criterion "The closing report reports no open threads and no incomplete arcs."

---

## 4. Chapter imbalance

| Chapter | Pages written | Pages derived | Match | Words | Avg. per page |
|---|---|---|---|---|---|
| 1 ("The Passenger") | 3 | 3 | Yes | 1194 | 398 |
| 2 ("The Cost") | 3 | 3 | Yes | 1189 | 396.3 |
| **Total** | **6** | **6** | **Yes** | **2383** | **397.2** |

Act boundaries match the derivation exactly:
- Setup: Page 1 (derived [1, 1]) ✓
- Development: Pages 2–5 (derived [2, 5]) ✓
- Resolution: Page 6 (derived [6, 6]) ✓

**Finding:** No chapter imbalance. All pages match their chapters, chapter sizes match the derivation, and act boundaries fall at the derived pages.

---

## 5. Flagged pages

| Page | Reason | Attempt | Word count | Rejection |
|---|---|---|---|---|
| 3 | TR-08: emitted commentary before prose | 3 | 438 (returned); 366 (prose only) | Retries spent; page accepted flagged |

**Flag ratio:** 1 of 6 pages = 0.167 (16.7%)
**Ceiling (`control.max_flagged_ratio`):** 0.1 (10%)
**Status:** **BREACH**

Page 3 violated TR-08 (technical specification section 8) by emitting commentary before the prose. The page's three retry attempts proceeded as follows:

1. Attempt 1: 395 words. Accepted by mechanical validation and all seven consistency checks K1–K7. Then invalidated by the chapter-close continuity audit (contradiction with earlier pages about the number of people aboard).
2. Attempt 2: 399 words. Rejected on K7 (undeclared character worked the sheet line; violation of FR-11).
3. Attempt 3: 438 words as returned. Rejected on structure (commentary before prose, TR-08 violation). Retries were spent; the page was flagged and accepted. The orchestrator wrote the prose portion only (366 words) to the page file.

The flag ratio breach is recorded in `audit.json`, line 126: `"flag_ratio_within_ceiling": false`. This is a defect against the acceptance criterion "Flagged pages do not exceed `control.max_flagged_ratio` of the total."

---

## 6. Continuity repairs

| Page | Contradicted pages | Contradiction | Supersedes | Repaired |
|---|---|---|---|---|
| 3 | Pages 2 and fact ledger | "Two men aboard" vs. three (Kael, Vex, Orin) | Previous state record for page 3 | Yes |

**Repairs spent:** 1 of `control.max_continuity_repairs` = 2
**Status:** Within ceiling

The contradiction was discovered by the chapter-close continuity audit at the end of chapter 1 (page 3, the last page of chapter 1). Page 3 stated the boat carried "two men" where page 2 and the fact ledger established three people aboard: Kael, Vex, and Orin. The orchestrator rewriting page 3 through the ordinary page path (B3 to B7) and appending a superseding state record resolved the defect. The chapter was re-audited and came back clean. Chapter 2 (pages 4–6) audited clean on the first pass.

**Finding:** One continuity repair, within budget, properly recorded and resolved. No defect here.

---

## 7. Superseded configuration values

**None.** The audit reports `"supersessions": []` (audit.json, line 143). No configuration values were superseded by derivation or precedence. `organization.pages_per_chapter` is `null`, so no conflict existed between `chapters` and `pages_per_chapter` to trigger FR-37 reporting.

---

## 8. Acceptance criteria — section 9 analysis

A run is accepted if it meets all of the following. Each is answered yes or no:

**Criterion 1:** "It produces `organization.pages_total` pages, grouped into chapters according to `derived.chapter_sizes`, honouring `derived.act_spans`."
**Answer:** **YES**. Six pages, two chapters of three pages each, acts at [1,1], [2,5], [6,6].

**Criterion 2:** "No character changes name, appearance or voice without narrative justification."
**Answer:** **YES** (by orchestrator validation, no defect reported). Mechanical check TR-11 and consistency checks K2–K4 cover this ground.

**Criterion 3:** "Every setting is described on its first appearance."
**Answer:** **YES** (by orchestrator validation, no defect reported against FR-03).

**Criterion 4:** "The closing report reports no open threads and no incomplete arcs."
**Answer:** **NO**. Three open threads (t1, t2, t3) remain unresolved. One character arc (Paine) is incomplete — declared to "discover he cannot control what matters most" but never tested against that discovery.

**Criterion 5:** "Flagged pages do not exceed `control.max_flagged_ratio` of the total."
**Answer:** **NO**. One page flagged of six = 16.7%, exceeding the 10% ceiling. The breach is 1.67 percentage points or 0.0667 absolute ratio points.

**Criterion 6:** "Reading the pages in order reveals no causal gaps, and chapter boundaries fall at narratively sensible points."
**Answer:** **PRESUMED YES** (no defects reported by orchestrator validation). Chapter boundaries fall at the end of page 3 and page 6, which are the end of the development act and the end of the story respectively — narratively sensible. Causal continuity was checked by the chapter-close audit and repaired once.

**Criterion 7:** "Each anchor page turns the story: the situation after it cannot return to what it was before."
**Answer:** **NO, WAIVED.** The A6 anchor-reversal gate (FR-27) failed three times in succession and exhausted `control.consistency_gate_max_attempts` = 3. The operator instructed that the gate be set aside so the calibration loop could be exercised. The run restarted from the staged bible with FR-27 waived. The payload states: "This run therefore does not satisfy FR-27 and no claim that it does can be supported. Report it as a waived requirement, on the operator's instruction, not as a passed check." The requirement was waived, not met.

**Criterion 8:** "`paths.manuscript` exists, is written in `story.language`, and contains every page in order under its chapter title."
**Answer:** **YES**. File exists at `stories/the-glass-ferry/story.md`, is written in English (`story.language: "en"`), contains six pages in order with chapter titles ("The Passenger" for chapter 1, "The Cost" for chapter 2).

**Criterion 9:** "Changing any single value in `organization` — page count, chapter count, chapter length or act proportions — produces a story of the new shape, with no other edit to the configuration, to prompts or to code."
**Answer:** **UNTESTED**. This criterion requires a configuration flexibility test that was not performed in this run. No defect was reported, but the criterion cannot be answered without a second run under a modified configuration.

**Criterion 10:** "No value supplied in `config.json` is ignored without being reported."
**Answer:** **YES**. `derived.supersessions` is empty; no values were superseded. All configuration values were either used as given or, in the case of derived values, computed and reported.

**Criterion 11:** "Continuity repairs do not exceed `control.max_continuity_repairs`, and every one is recorded in the closing report."
**Answer:** **YES**. One repair performed, against a budget of two. The repair is recorded in section 6 above.

**Criterion 12:** "Writing a second story leaves every file of every earlier story unchanged, and the earlier manuscripts still read exactly as they did."
**Answer:** **UNTESTED**. Only one story exists in the workspace. This criterion requires a multi-story test. The workspace isolation rules (FR-42, invariant 7) are enforced in code, so the criterion is likely satisfied, but cannot be verified from this run alone.

**Criterion 13:** "A workspace, taken on its own, contains everything needed to read, audit or resume its story."
**Answer:** **PRESUMED YES**. The workspace at `stories/the-glass-ferry/` contains the bible, the state log, the pages, the manuscript, the report, and the configuration copy. By design, it is self-contained.

**Criterion 14:** "Every page was written by one invocation and judged by another, and the record of the run shows both."
**Answer:** **PRESUMED YES**. The functional specification 2.4 (delegated form, TR-09) requires that the page-writer call (B3) and the consistency-checker call (B5) be separate invocations. The measured run under version 2.3 violated this, running the check as a separate pass inside the same session. This run (under 2.4) should satisfy the requirement, but no record was provided in the audit to verify which invocation wrote which page. No defect was reported by the orchestrator.

**Criterion 15:** "No agent definition contains a value that belongs in `config.json`."
**Answer:** **PRESUMED YES** (by design review controls V-13, not verified in this audit). No defect was reported.

---

## Ancillary findings — critical gate failure and data integrity

Two matters require explicit reporting because they affect confidence in the run's output:

### A6 Anchor-reversal gate instability and waiver

The A6 gate (FR-27) is responsible for enforcing that every anchor page states a reversal — a moment where the story turns and cannot return. The gate has two halves:

- **Arithmetic half** (coverage, chapter tiling, invariant 7, sheet format, act spans, unique objectives, roster use): Executed in code, passed.
- **Judgement half** (FR-27: each anchor page turns the story): Delegated to a consistency check, executed three times, failed all three times, exhausted the budget of `control.consistency_gate_max_attempts` = 3.

Under functional specification §5 Phase A, this is an abort condition. The run did abort.

**Operator intervention:** The operator then instructed that the anchor-reversal check be set aside and the run restarted from the staged bible. The calibration loop was exercised to adjust the length parameters. The run therefore proceeded and completed.

**Gate instability — evidence of unsafe behaviour:**

On the second attempt, the gate **failed page 2 on text byte-identical to the text it had passed on the first attempt.** The gate examined the same input (page 2's objective and content) and returned opposite verdicts with no intervening change to the text. This is evidence of non-determinism in the gate's judgement, and the verdict that passed was unsafe.

The defects migrated rather than resolving across repair attempts:
- Attempt 1: Gate failed page 5
- Attempt 2: Gate failed page 2
- Attempt 3: Gate failed page 3

Each repair correctly addressed the failure it was given, but invalidated a neighbour that had previously passed. This pattern is consistent with a gate that is sensitive to context in the summary window or to the exact phrasing of adjacent pages, rather than a gate that is judging the anchor pages in isolation against the requirement. Every repair was correct for the page it was asked to fix; the instability is in what the gate accepts from call to call.

**Consequence:** The run's claim that each anchor page turns the story is unsubstantiated. FR-27 was waived, not satisfied. The specification requires acceptance criteria to include this check (section 9, criterion 7), and this run does not meet it.

### State-record extraction edits

The state log is built by an orchestrator-owned call that extracts the summary line, character states, threads, and facts from the finished prose of each page. On three occasions, the orchestrator edited what this call returned before writing it to the ledger:

1. Page 1: A fact that attributed Kael's thirty years to Paine was corrected
2. Page 3: Pronouns for Vex were corrected
3. Page 4: A state that said "near shore" where the page shows the far shore was corrected

The ledger is therefore not a purely machine reading of the prose. This is acceptable and necessary — the extraction call is fallible and the orchestrator's role includes reconciling the extracted facts against the prose — but it means the state log is a human-guided record, not an automated one. This is noted for transparency: any audit of the run that relies on the state log as the sole source of truth would be incomplete if it did not account for these three edits.

---

## Summary of defects

The run exhibits **three defects against acceptance criteria:**

1. **Three open threads** (t1, t2, t3) from page 1 that are never closed. These are narrative promises made by the setup that the story does not keep.

2. **One incomplete character arc** (Paine: declared to discover he cannot control what matters most, but never tested against that discovery; appears on page 1 only).

3. **Flagged page ratio exceeds ceiling** (1 of 6 pages = 16.7%, ceiling 10%). Page 3 violated TR-08 (commentary before prose) and retries were spent.

Additionally, **FR-27 (anchor-reversal requirement) was waived by operator instruction.** The gate failed three times in succession and exhibited unsafe behaviour (same input, opposite verdicts). The run cannot claim to satisfy this requirement.

**Verdict:** The run does **NOT** meet the acceptance criteria of functional specification §9. It fails criteria 4 (open threads and incomplete arcs), 5 (flagged page ratio), and 7 (anchor page reversals, waived).

The defects in the run are:
- Insufficient closure of narrative threads opened on page 1
- Incomplete character arc for Paine
- One page that violated structure rules and was accepted flagged

The defect in the specification is candidate only:
- The anchor derivation produces three anchor pages in a six-page story, with two of them adjacent (pages 2 and 3). This concentration may be a source of the gate instability, but cannot be concluded without evidence from additional runs. Recommendation: Review whether three anchors in six pages is appropriate, or whether the derivation of section 2.2 should space anchors further apart in small stories.

---

## Evidence trail

- **Story text:** `stories/the-glass-ferry/story.md`
- **Audit data:** `.tmp/audit.json` (computed by orchestrator)
- **Beat sheet:** `stories/the-glass-ferry/bible/beats.json`
- **Configuration:** `config.json` at repository root, configuration copy at `stories/the-glass-ferry/runs/` (not specified in payload, but per FR-03)
- **State log:** `stories/the-glass-ferry/state/deltas.jsonl` (referenced in payload, not read; contains the three edited records noted in Ancillary Findings section)
