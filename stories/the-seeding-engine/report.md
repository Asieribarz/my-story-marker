# Closing report — `the-seeding-engine`

**Run** 2026-09-18T10-00 · **Specs** v2.4 · **Config** v2.4 · **Form** hand-orchestrated (the build-inventory orchestrator does not exist; a session executed in code every step functional §5.0 assigns to code and delegated every step it assigns to an agent) · **Report call** `closing-auditor`, attempt 1 (FR-48).

Every figure below was computed by the orchestrator at C1–C3 (FR-25, FR-19). Nothing here is recomputed. What follows is judgement about what those figures mean.

---

## 1. What was produced

Ten pages in four chapters, 4139 words of page prose, assembled into a manuscript of 4161 words under four chapter titles (C4, FR-29).

| Configured / derived | Written |
|---|---|
| `pages_total` 10 | 10 pages |
| `derived.chapter_sizes` [3, 3, 2, 2] | 3 / 3 / 2 / 2 |
| `derived.act_spans` 1-2 / 3-8 / 9-10 | boundaries fell exactly there |
| `derived.anchor_pages` [3, 5, 8] | anchors on 3, 5, 8 |
| `page.target_words` 380 ±0.20 → 304-456 | every page inside the band |

The story as written is the story as configured. There is no shape discrepancy to report.

One structural observation the derivation produced rather than the run: at `pages_total` 10 with four chapters, the setup act (1-2) ends inside chapter 1, so page 3 is simultaneously the first development page, the first anchor, and the chapter-1 closing page. **Every defect of this run landed on that page** — both content retries (2 of 2) and both continuity repairs (2 of 2). That is not proof of causation from one run, but it is the kind of load concentration the derivation creates at small `pages_total`, and it is worth watching in the next short run before it is called coincidence.

## 2. Open threads

**None.** Seven threads opened and all seven closed: t1 (p1→p9), t2 (p1→p5), t3 (p2→p3), t5 (p4→p6), t6 (p5→p9), t7 (p7→p8), t8 (p8→p10). No promise the story made was left unkept, and there is therefore no deliberate-open ending to defend either: this story closes.

One item for the record, not a finding against the story: the identifiers run t1, t2, t3, t5, t6, t7, t8 — **t4 does not appear**. Threads are minted at the moment of opening (FR-35) and the register is a replay projection, so a gap means either a thread minted and never recorded, or a counter incremented without an opening record. The payload asserts seven opened and seven closed, which is internally consistent, so I do not contradict it. But an identifier sequence with a hole in it is a thing the replay should be able to explain, and it cannot be explained from the numbers I was given. Recorded as an open question against the state log, not as an open thread.

> **Orchestrator note on t4, added after the report call.** The auditor is right that the gap needs an explanation and right that its payload could not supply one. The explanation is this: t4 was minted in the *first* state record for page 3 — Teo's demand that the first line of the recall order be read aloud — and that record was superseded by the first continuity repair, which rewrote the page without that demand. Replay prefers the superseding record (TR-04c), so the thread that carried t4 correctly disappears from the register along with the prose that opened it, and nothing was left dangling. But the identifier does not come back into the pool, because minting is monotonic. This is a real and unrecorded consequence of FR-35 meeting FR-40: **a continuity repair can retire a thread identifier, and the replay then shows a hole it has no way to account for.** The auditor could only see the hole; it is named here so that a later reader does not have to reconstruct it from the log. It belongs as an open issue against FR-35 / TR-04b.

## 3. Incomplete arcs

**None.** All four characters reach the final state their Phase A sheet declares, and in three of the four the logged state is a stronger statement of the declaration rather than a bare match:

- **c1 Maren Vosk** — declared: chooses what the valley gets, cranks the valve alone, walks out carrying work and debt in the open. Logged (p10): out of the valley's machinery, carrying the debt in the open, "having told the whole of it to the one person owed an account." Met, and the account-giving is the declared debt made concrete.
- **c2 Idris Calloway** — declared: takes the governor with his own hands so someone else can walk out. Logged (p10): holding the governor load inside the sealed vault; he does not leave. Met exactly, including the cost.
- **c3 Teodora Rask** — declared: released from the load, reading the weather rather than ruling it. Logged (p10): no longer ruling the valley's weather, only reading it aloud. Met, and it is the premise's tentative ending delivered verbatim in effect.
- **c4 Sabel Onwe** — declared: has chosen the valley's future on the engineers' word and is the first person Maren faces with the result. Logged (p10): has her rain back on the valley's own terms, and the full account of what it cost. Met.

## 4. Chapter imbalance

**None.** Words per chapter 1232 / 1305 / 810 / 792; pages per chapter 3/3/2/2 against `derived.chapter_sizes` [3,3,2,2]. The word spread across chapters is a direct function of page count (411 and 396 words per page respectively in the two-page chapters — both inside the band) and is not an imbalance.

Act boundaries fell where `derived.act_spans` put them. The act-1/act-2 boundary does not coincide with a chapter boundary; nothing in §9 or §2.2 requires that it should, and the beat sheet honoured the span it was given.

## 5. Flagged pages

**None. Flag ratio 0.00 against a ceiling of `control.max_flagged_ratio` 0.10.** No page exhausted `control.max_retries_per_page`; every page was accepted on its merits rather than on budget exhaustion.

**Length, with the previous run as the comparison.** Two content retries this run, both K-failures on page 3 (one K4 world-rule, one K3 arithmetic-in-dialogue); **zero length failures**, against six of seven in the measured run of `the-cold-lamp`, all six from above. Raising `page.target_words` to 380 did what OI-02 predicted with the evidence it had. But the distribution moved rather than centred: word counts were 411, 417, 404, 439, 410, 456, 402, 408, 381, 411 — **mean 413.9, and not one of the ten pages came in at or below the 380 target**. Page 6 sat at 456, exactly on the ceiling, with zero margin. The writing call is treating the upper edge of the tolerance band as its target, not the target as its target. At 380 that is harmless because the band absorbs it; the finding is that **`page.length_tolerance` is doing the work `page.target_words` is supposed to do**, and any future tightening of the tolerance will re-create the retry storm rather than tighten the prose. This belongs against OI-02 as a second measurement, not against this run.

## 6. Continuity repairs (FR-40)

Budget `control.max_continuity_repairs` = 2. **Two performed, both on page 3, each recorded as a superseding state record. The budget was spent in chapter 1 and two later true findings therefore shipped unrepaired.**

| # | Chapter | Page | Contradiction | Outcome |
|---|---|---|---|---|
| 1 | 1 | 3 | Descent arrived on the salt at the ninth turn of a twelve-turn pass | Repaired, superseding record |
| 2 | 1 | 3 | After repair 1, the array's voice reached them by harness relay at the seventh turn, where page 2 had established no relay past the third switchback | Repaired, superseding record |
| — | 1 | 3 | A line of dialogue gave Maren a wrong sum | Fixed via a third rewrite prompted by the consistency check (K3), not by the auditor; charged to the retry budget, not the repair budget |
| 3 | 2 | 6 | "It was given away an hour ago" of the master key, where page 6's own narration places the surrender some twenty minutes earlier | **Unrepaired — budget spent** |
| 4 | 3 | 7 | "Hail on the hour and off it", where the same page earlier fixes the hail at the quarter hour (digest 03: "hail timed to the quarter hour") | **Unrepaired — budget spent** |

Chapter 1 re-audited clean after repair 2; chapter 4 was clean on first audit.

**Severity of the two that shipped: low, individually.** Both are single clauses of dialogue contradicted by narration on the same page, both concern elapsed time only, and nothing downstream depends on either — the continuity auditor itself filed the page 7 item as the weakest kind of true finding, and I agree with that characterisation on the evidence. A reader will not be stopped by either.

**Severity of the mechanism that let them ship: high, and it is a defect in the specification, not in the run.** `control.max_continuity_repairs` is a *per-run* budget (FR-40: "up to `control.max_continuity_repairs` per run"), audited *per chapter* (FR-39). One page in chapter 1 consumed the whole run's repair capacity — and consumed it legitimately, on two real contradictions, the second of which the first repair introduced. From page 4 onward the chapter-close audit was still running, still finding true defects, and structurally unable to act on any of them. The audit branch that §8 added to remove the first run's committed-calendar defect **was live for one chapter of four**. The rationale for bounding repairs is sound (a rewrite invalidates what later pages assumed), but a per-run bound makes the audit's power a function of where in the story the first defect happens to fall, which is arbitrary. This is the same class of defect as the sheet budget silently doubling as a cast budget: a number that is bounding one thing while being spent on another. It should be carried as an open issue against FR-40 / `control.max_continuity_repairs`, and the run that supplies the evidence is this one.

Related, and also a specification gap rather than a run defect: repair 2 exists only because repair 1 created it. The flow (B9→B10→B9) correctly re-audits after a repair, which is what caught it — but nothing in FR-40 says whether a defect *introduced by a repair* should be charged to the same budget as a defect the story arrived with. Here it was, and that is what exhausted the budget on a single page.

## 7. Superseded configuration (FR-37)

**None. No value supplied in `config.json` was ignored.** `organization.pages_per_chapter` was null, so `organization.chapters` superseded nothing, and the precedence rule of §2.2 was never exercised.

This section is required to exist even when empty, and it should be read as empty rather than as clean: **FR-37 is untested by this run in the delegated form.** The only measurement of the precedence path remains the one in `stories/the-cold-lamp/report.md`. A run that supplies both `chapters` and `pages_per_chapter` in conflict, and shows the supersession reported at start-up *and* here, is still owed.

## 8. Acceptance against functional §9

| # | Criterion | Answer | Evidence |
|---|---|---|---|
| 1 | `pages_total` pages, grouped per `derived.chapter_sizes`, honouring `derived.act_spans` | **Yes** | 10 pages, 3/3/2/2, act boundaries at 1-2 / 3-8 / 9-10 as derived (C3) |
| 2 | No character changes name, appearance or voice without narrative justification | **Yes** | Per-page consistency check (K1–K7) passed at first attempt on 9 of 10 pages; page 3's two failures were K4 and K3, neither a character-identity failure. No closing measurement of this criterion exists — see the gap noted below |
| 3 | Every setting described on first appearance | **Yes, on weaker evidence** | Carried entirely by the per-page `consistency-checker` calls; C1–C3 compute nothing against it. No first-appearance ledger was produced |
| 4 | Closing report reports no open threads and no incomplete arcs | **Yes** | C1: 7 opened, 7 closed, none open. C2: 4 of 4 arcs reach their declared final state |
| 5 | Flagged pages within `control.max_flagged_ratio` | **Yes** | 0 flagged, ratio 0.00 against 0.10 |
| 6 | No causal gaps on a straight read; chapter boundaries narratively sensible | **Yes, with two recorded exceptions and one live risk** | The two unrepaired items (p6, p7) are intra-page time contradictions, not causal gaps. The final-day timing risk in §9 below is the one item that could read as a gap |
| 7 | Each anchor page turns the story | **Yes, on the weakest evidence in this report** | Anchors 3, 5, 8 passed the A6 reversal judgement — made by the orchestrator session, because OI-12 leaves that judgement with no agent, and assessed by the criterion OI-07 says nothing calibrates. The answer is yes; the check behind it is the one whose failure mode is silent |
| 8 | Manuscript exists, in `story.language`, every page in order under its chapter title | **Yes** | C4 assembled 4161 words from `pages/` under four chapter titles |
| 9 | Changing one `organization` value alone produces a story of the new shape | **Yes — demonstrated** | This run is the demonstration: 10 pages / 4 chapters against the earlier 20 / 5, with no edit to prompts, code or any other config value, and the derivation produced [3,3,2,2], 2/6/2 and anchors 3/5/8 unaided |
| 10 | No supplied value ignored without report | **Yes, vacuously** | Nothing was superseded (§7) |
| 11 | Continuity repairs within `control.max_continuity_repairs`, every one recorded | **Yes** | 2 of 2, both recorded above with page and contradiction |
| 12 | A second story leaves every earlier story unchanged | **Yes** | This run wrote only inside `stories/the-seeding-engine/`; `the-cold-lamp` untouched (FR-45, I-9) |
| 13 | A workspace alone suffices to read, audit or resume | **Yes** | Bible, pages, state log, chapter digests, manuscript, config copy and per-call traces all present in-workspace |
| 14 | Every page written by one invocation and judged by another, and the record shows both | **Yes, structurally — for the first time** | B3 and B5 were separate delegations to `page-writer` and `consistency-checker` under FR-46, each labelled per FR-48. This is the criterion the measured `the-cold-lamp` run failed by running the check as a second pass in the same session; the delegated form fixes it in substance, not only in form |
| 15 | No agent definition contains a value belonging in `config.json` | **Not verified by this run** | V-13 is a review control performed by a person against `.claude/agents/*.md`, and nothing in this run measured it. I will not answer yes on a check that was not run |

**Verdict: the run is acceptable.** Fourteen criteria answered yes; one (15) is unverified by this run and must be answered by V-13 review, not by me. The story is complete, closed, balanced, unflagged, and within every budget it was given.

## 9. Findings that are not acceptance failures

**The final day is the one narrative risk I would not sign off without a reading.** The auditors filed it as a soft risk because no page states a walking pace, and therefore no fact entered the ledger for the audit to bite on. But the arithmetic is available from the digests: the corridor is nine kilometres (digest 03), it was leapfrogged in two loads — which is three traverses, roughly 27 km on steel grating carrying a 30-kg shaft and an 80-kg gear case — and on top of that the full thirty-one-step handover, all between dawn and the eleven o'clock the last page dates the end to. That is not impossible to defend, but it is tight enough that a reader with a pencil can reach it, and it is the only soft risk in this run that a reader could take for an error rather than a subtlety. **The mechanism that let it through is OI-08**: what counts as a fact a page asserts is undefined, and an *unstated* quantity — a pace, a ration — cannot enter the fact ledger at all, so the continuity audit is structurally blind to contradictions that live in the arithmetic between two stated facts. Both this and the water risk (page 2 files five days; page 4 has three litres at the end of day 3; reconciling needs a ration figure no page states) are the same failure, and they are the strongest evidence this run produced for OI-08.

The third soft risk — pages 9 and 10 both running counts that terminate at thirty-one (Teo's handover steps, Maren's crank turns) — is arithmetically exact and is a craft choice, not a defect. It may well be deliberate. It needs a reader's eye, not a repair.

**A malformed agent return has no branch.** One `page-writer` call returned a report wrapping the prose (TR-08) and the prose was lost; it was re-requested and correctly not charged to `control.max_retries_per_page`. That handling was right, but it was improvised: FR-33 exempts *endpoint* failures (timeout, rate limit, transport), and B6 governs *rejected content*. A return that is well-delivered and badly shaped is neither, and the specification says nothing about it — including nothing about how many times it may recur before the run should stop. This is the fifth member of the family the `the-cold-lamp` report named: a real failure mode with no branch to handle it. It should be opened as an issue against FR-33 / TR-08.

**FR-18 worked, and worked well.** After the chapter-2 audit warned that a 110-kg crank on a goat sled could not climb the vault stair, the orchestrator amended the page 7 beat entry to split the crank *before* page 7 was written, and re-ran the A6 arithmetic against the amended sheet, which still passed. That is exactly the procedure FR-18 describes, performed at the only moment it is cheap, with the gate re-checked rather than assumed. The resulting split (a 30-kg shaft and an 80-kg gear case, digest 03) then carried a character beat — Maren giving Idris the part she could not replace. This is the run's best evidence that the beat-sheet amendment path is sound.

## 10. Readiness for an unattended run

**Not ready.** Nothing in this run's numbers argues against the delegated form — it produced a clean story and, for the first time, satisfied §9 criterion 14 in substance. What blocks unattended operation is unchanged and is not measurable from a good outcome:

- **OI-07 with OI-12** — the anchor-reversal gate is the one check whose failure is silent, it has no agent of its own, and in this run it was judged by the session playing the orchestrator. A run with nobody watching has no way to notice it passing something it should not.
- **OI-10** — the consistency, continuity and audit calls, this one included, ran at composition temperature, because an agent definition cannot carry one. Every judgement in this report was made by a call that has no mechanism to be made deterministic.
- **OI-11** — `page-writer` was instructed, not prevented, from reading beyond its payload; it was handed its context as a path, and each call's tool use is consistent with having read only that path. "Consistent with" is the strongest statement available, and it is not the statement FR-08 needs.
- **The repair budget defect of §6** — a per-run bound on a per-chapter audit, which disarmed the audit after chapter 1 here and would do so again, unsupervised, with nobody to notice that the later chapters' findings were being filed rather than fixed.

The first three are known and carried. The fourth is new evidence from this run, and it is the one I would fix first, because it is the only one whose cost is already visible in the shipped manuscript.
