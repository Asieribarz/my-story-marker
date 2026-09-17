# Closing report

| | |
|---|---|
| **Run** | `runs/2026-09-17T08-15` |
| **Branch** | `retroceso` |
| **Configuration** | `config.json` v2.3, copied into the run directory at start-up (TR-02) |
| **Specifications** | Functional v2.3, Technical v2.3 |
| **Premise (run argument)** | A disgraced salt-caravan guide recrosses a drying inland sea to learn why a well-town has stopped lodging its water tally, taking a child who knows the line of cairns by heart and has no voice to say it. |
| **Story id (run argument)** | `the-salt-road` |
| **Deliverable** | `story.md` — *The Salt Road*, 10 pages, 3 913 words of prose |
| **Verdict** | **Accepted with defects.** Nine of ten acceptance criteria met; criterion 6 is not met, and four continuity defects ship unrepaired because `control.max_continuity_repairs` was exhausted at the first chapter close (§6). |

This run is the first to execute the machinery added in v2.2 and v2.3: the separated cast ceiling, the fact ledger, the chapter-close continuity audit, and the workspace boundary. It is also the first in which the judgement calls went to an endpoint that had not written the material. That single change accounts for most of what follows.

---

## 1. Acceptance criteria (functional specification §9)

| # | Criterion | Result |
|---|---|---|
| 1 | `pages_total` pages, grouped by `derived.chapter_sizes`, honouring `derived.act_spans` | **PASS** — 10 pages, chapters of 4 / 3 / 3, acts 2 / 6 / 2, all derived from `config.json` and never restated |
| 2 | No character changes name, appearance or voice without justification | **PASS** — three violations caught by the consistency agent and repaired before commit (§5) |
| 3 | Every setting described on its first appearance | **PASS** — checked in code at the A6 gate; all four sheets carry appearance and atmosphere |
| 4 | No open threads, no incomplete arcs | **PASS** — 7 of 7 threads closed, 4 of 4 arcs reach their declared final state (§2, §3) |
| 5 | Flagged pages ≤ `control.max_flagged_ratio` | **PASS, at the limit** — 1 of 10, ratio 0.10 against a ceiling of 0.10. One more flag would have failed the run |
| 6 | Reading the pages in order reveals no causal gaps | **FAIL** — three hard contradictions survive in the committed text, all found by the continuity audits and none repairable once the budget was spent (§6) |
| 7 | Each anchor page turns the story | **PASS, and for the first time verified** — pages 3, 5 and 8 were passed by an independent judge against the text, not by the regular expression alone. See §5 on OI-07 |
| 8 | `paths.manuscript` exists, in `story.language`, every page in order under its chapter title | **PASS** — `story.md`, English, three titled chapters |
| 9 | Changing any single value in `organization` produces a story of the new shape | **PASS, and exercised in anger** — the operator edited `pages_total` from 20 to 10 and `chapters` from 5 to 3 between A0 and Phase A, and the whole story reshaped with no other edit to configuration, prompts or code. This criterion was recorded NOT TESTED in the previous run |
| 10 | No configuration value ignored without being reported | **PASS** — `organization.pages_per_chapter` is null, so no supersession arose; the derivation reports one would have been |

---

## 2. Thread ledger (C1 — FR-16, FR-19)

Threads are minted when they open (FR-35, TR-04b). This is the replay of `state/deltas.jsonl`, preferring superseding records (TR-04c).

| Thread | What it promised | Opened | Closed |
|---|---|---|---|
| t1 | What is inside the sealed tally-case | p1 | p5 |
| t2 | The eleven Sev will not speak about | p1 | p10 |
| t3 | What the Office retains Oduin for | p2 | p6 |
| t4 | Who emptied Cairn Nine | p3 | p10 |
| t5 | Where Kethra's tally is | p4 | p5 |
| t6 | Whether a keeper with no voice can lodge a tally | p5 | p10 |
| t7 | Why no cairn stands where the count ends | p7 | p8 |

**Unclosed: none. Closed without an opening: none.**

---

## 3. Character arcs (C2 — FR-02)

Checked in code against the final state declared in Phase A, using the last state record that mentions each character, and confirmed against the committed prose by the chapter-3 audit.

| Id | Character | Declared arc | Closes | Reached |
|---|---|---|---|---|
| c1 | Sev Marrow | unforgiven → answerable | p10 | Yes — signs beneath the count and puts the eleven names in with her own |
| c2 | Tallow | unheard → heeded | p10 | Yes — lodges the count in her own hand, and the line becomes hers to give |
| c3 | Oduin Reck | bought → honest | p6, confirmed p9 | Yes — gives back the forty, asks for his name in the book, then gives up his camels |
| c4 | Berec Sund | unquestioned → struck off | p10 | Yes — enters the lodgement himself, with his own ring, and the Office has another factor by the afternoon |

**Incomplete arcs: none.** c3 completes earliest and is absent from page 10 by the cast ceiling; his final state is reported there by another character's pen rather than shown, which the audit notes as a weakness rather than a failure.

---

## 4. Balance, length and flags (C3)

**Length (FR-10).** Band 280–420 words at `page.target_words` 350 ± 20 %. Nine of ten pages in band. Mean 391.

| Chapter | Title | Pages | Words |
|---|---|---|---|
| 1 | The Third Season | 1–4 | 1 542 |
| 2 | The Count | 5–7 | 1 170 |
| 3 | Off the Line | 8–10 | 1 201 |
| | | **total** | **3 913** |

Chapter 1 holds four pages to the others' three, so the spread is structural. Per-page means are 386 / 390 / 400. **No chapter imbalance to report.** Acts: setup 797, development 2 305, resolution 811 words, against a page split of 2 / 6 / 2. Proportional.

**Flagged pages (FR-19): one.** Page 10, accepted at 426 words, six over the ceiling, after `control.max_retries_per_page` was spent. Its consistency verdict on the committed text is PASS on all seven checks, so the flag is length and not content — a distinction the state record carries and the acceptance criterion does not.

**Content retries.** The final ledger records 8 across 6 pages; counting the records later superseded by continuity repairs, 12 were spent in the run.

| Page | Retries | Rejected by |
|---|---|---|
| 1 (superseded) | 2 | FR-10 at 424, then K1 appearance and K2 voice, then FR-10 at 428 |
| 2 | 1 | K4 — a notice implying cisterns under cairns other than Four and Nine, against r3 |
| 3 (superseded) | 2 | K1 — a pace figure that put the crossing at an eighth of the sheeted distance |
| 5 | 1 | K5 — the anchor's closing clause, the cost of recrossing, was absent from the page |
| 6 | 2 | K5 — the party never went back on to the crust; then K6 — the repair put a character in two places |
| 8 | 1 | K1 — the sun rising on the wrong side, which the setting sheet's whitewash proves |
| 9 | 1 | K4 — the last leg walked at twice the validated pace |
| 10 | 2 | K4 and K5 — a strike-off the world rules cannot support, and a count contradicting a committed page; then twice over the length band |

Six of twelve retries were length, and every one was over the ceiling. **FR-10 binds from above**, exactly as the previous run measured, and this run adds a second finding: the repairs that answer a consistency failure almost always lengthen the page, so a page that passes K1–K7 on its third attempt tends to fail FR-10 on the same attempt. Pages 1 and 10 were both lost that way.

**Endpoint failures (FR-33): none.**

---

## 5. The A6 gate, and what an independent judge costs

**The gate failed four times before it passed.** `control.consistency_gate_max_attempts` was 3; it was raised to 5 by the operator, mid-run, after the third failure, and the fifth attempt passed six checks of six.

| Attempt | Failed | Nature of the failure |
|---|---|---|
| 1 | 5 of 6 | Anchor page 5 used reversal vocabulary over a continuation; Oduin's arc announced, not dramatised; the return water unsourced; two causal links by authorial fiat |
| 2 | 2 of 6 | One load of water asked to cover four legs; the deadline stated two ways |
| 3 | 3 of 6 | A whole stage walked in the hours the crust will not bear; the document proving the child's standing left eighty miles away; the last page carrying nine pieces of business at 350 words |
| 4 | 2 of 6 | Moving a sabotage off-page broke three things at once; two elements planted and no longer paid |
| 5 | none | — |

**This is the run's principal measurement, and it is about the previous run, not this one.** The run of 2026-09-15 passed A6 on the first attempt, and its own report says why (D2): the judge was not an independent endpoint. Put in front of a judge that had not written the beat sheet, the same gate rejected four successive versions, and every rejection named a defect that was real and locatable. **`consistency_gate_max_attempts` = 3 was calibrated against a rubber stamp.**

Two consequences follow, and both are specification defects rather than run defects:

- **Phase A has no degraded exit and Phase B does.** After `max_retries_per_page` a page is accepted flagged and the run continues (TR-16); after `consistency_gate_max_attempts` the run dies, and because Phase A is atomic it dies leaving nothing. That asymmetry is invisible while the judge approves its own work and fatal once it does not.
- **The gate has no severity.** TR-14c's "FAIL if any check fails" is right for a page verdict and too blunt for A6, which mixes coherence (the water does not add up) with craft (the last page has too much business). Only the first justifies redoing A5.

**OI-07 is answered in this run, and the answer is not reassuring.** The lexical proxy passed all three anchor objectives at every attempt, including attempt 1, where the independent judge found page 5 to be "exactly the reversal vocabulary this check exists to catch — a relabelling of page 4's discovery". The regular expression and the judge disagreed, the judge was right, and nothing in the mechanical gate could have told them apart. **OI-07 and TI-10 should remain blocking for any unattended run.**

---

## 6. Continuity (FR-38 to FR-40), and the branch the previous run did not have

The chapter-close audit found defects at all three chapter closes. `control.max_continuity_repairs` is **2 per run**, and chapter 1 consumed both.

**Chapter 1 — two repairs spent, both applied.**

1. *Hard, pages 1 and 3.* Page 1 set the deadline at "noon on the fifth day from this one", which resolves to day six, while page 3 has Sev say "three days of book left" at first light of day two. Repaired by rewriting page 1 through the ordinary page path. The rewrite also brought the page inside the FR-10 band, which cleared the flag it had been carrying — **a continuity repair silently mended an unrelated defect**, which is worth knowing before anyone tunes either budget.
2. *Soft, pages 3 and 4.* Under r2 the party could not leave Cairn Nine at sunrise, so a day lying up fell unrecorded between the two pages and its water was never charged against page 3's four-cask sum. Repaired on page 3. The first attempt at this repair ran past the page's own ending and was rejected at B5; the second passed.

A third finding — that the nine days of page 1 and the eleven of page 3 leave the child exactly one cold window for the Cairn Nine to landing leg — was examined and **not** a defect: that leg is one window by the settings sheet. It is recorded here because a later reader will re-derive it.

**Chapters 2 and 3 — four defects found, none repairable.**

| Pages | Severity | Defect |
|---|---|---|
| 5, 4 | **hard** | Page 5 has Sev say "You have been home half a day" inside the same unbroken beat in which page 4 ends, which is the moment of arrival |
| 9, 3 | **hard** | Page 9 finds Cairn Four's Office wax "whole" four days after the party drew the cistern full at page 3. The party has no Office stamp |
| 9, 10 | **hard** | Page 9 ends on the Kethra nail empty; page 10 takes four Kethra seals off their nails |
| 6, 5 | soft | Tallow writes three times running across the chapter boundary, against a sheet that forbids repeating a sign |

Each has a one-clause repair, recorded in the run directory. None could be applied.

**The finding is the budget, not the defects.** Two repairs per run was sized when nothing was looking for a third. An independent auditor reading a fact ledger finds defects at a rate of two to three per chapter close, and they are precisely the defects no per-page check can see: three of the six are contradictions between pages that never appear in the same context. This is the failure class that the previous run hit blind (its D8) and that FR-38 to FR-40 were written to catch. **The mechanism works. The budget does not.** `control.max_continuity_repairs` should scale with `organization.chapters`, or be per chapter close rather than per run.

**What the audits cleared.** The day-one-to-day-five calendar holds on every page; cask and cistern arithmetic balances outbound against return; the distances agree, two windows of eighty thousand paces against the eighty miles the setting sheet declares; and the child's eleven days at Cairn Nine interlock exactly with her nine days at the Office. A calendar consistent across ten pages is the specific thing the previous run could not achieve, and it was achieved here by repairing page 1 the moment the ledger exposed it.

**Unpaid promises, reported under FR-19.** Two things are set up and never returned to: Oduin's two camels, left in doubt on page 9 and never answered; and the order striking Cairn Four from the line, which convicts nobody and is never withdrawn, so Sev rebuilds a cairn that is still struck off on paper.

---

## 6b. Context budget, measured against §7 of the technical specification

Every assembled context was written to the run directory and measured, converted at the specification's own 1.35 tokens per word.

| Page | Words | ≈ Tokens | What it carries |
|---|---|---|---|
| 1 | 958 | 1 293 | No digests, no summaries, no bridge |
| 5 | 1 567 | 2 115 | One digest, three summaries, no bridge (chapter opening, TR-12) |
| 8 | 1 989 | 2 685 | Two digests, three summaries, no bridge (chapter opening) |
| 9 | 2 190 | **2 956** | Two digests, three summaries, bridge — the worst case |

The specification budgets **≈1 700 input tokens** for the worst case. The measured worst case is **≈2 956, some 74 % over**, and it is worse than the previous run's 2 090 despite this story having three chapters where that one had five.

**The cause is the v2.2 fix itself.** Separating `context.max_characters_per_page` from `context.max_settings_per_page` was the right change — it retired the two-hander problem the previous run suffered without knowing it, and this story has three-handed scenes because of it. But it also means a page now loads five sheets where the old shared budget of three loaded three, and a character sheet runs 90 to 120 words. Roughly 600 words of every context above is sheet payload that the old configuration could not have carried.

The design property still holds: the payload is bounded, and grows with `organization.chapters` and the two ceilings, never with `organization.pages_total`. But §7.1's per-call figure was computed against the shared budget and has not been revised. **It should be recomputed against the separated ceilings before it is used to estimate cost**, which is the other half of TI-01.

---

## 7. Deviations from the specification

**D1 — The system in §12 was not built; the run was orchestrated by hand.**
`model.id` and `model.max_output_tokens` are null (TI-01), and none of the orchestrator modules, prompt templates or test modules of §12 exist. The deterministic parts were written as code and executed: configuration load and derivation, invariants I-1 to I-5 and I-8 to I-9, the A6 mechanical gate, FR-10 and FR-11, `assemble(N)`, the state-log replay, the digest bound, thread and arc replay, chapter balance and manuscript assembly. Every mechanical number in this report is a measurement. The code lives outside the repository (TI-09).

**D2 — TR-09 is satisfied in substance for the first time.**
The A6 judgement, the K1–K7 verdicts and the three chapter-close audits were issued to endpoints that had not written the material and had no access to the reasoning that produced it. The previous run satisfied TR-09's form and not its substance and said so. The cost is visible in §5 and §6: four gate rejections and eight continuity defects that the earlier arrangement would not have surfaced. **OI-05 and TI-05 can be closed on the evidence of this run, in the direction of "necessary and expensive".**

**D3 — One agent served every page instead of one call per page.**
§12.2 specifies Agent 3 as a stateless call. Here a single consistency agent held the bible and was resumed per page. That is cheaper and gives better cross-page judgement, and it is not what the specification says. Two of its findings — the repeated camel-directed lines, and the counting tic being leaned on — were only available because it remembered earlier pages, which suggests the specification's statelessness is a cost rather than a safeguard.

**D4 — `beats.json` asked for something the world rules forbid.**
Beat 10 requires Sund "struck off under the article he was quoting". Article five governs towns, lines and cases; it grants no power over an officer. The page substitutes a rule-true equivalent — the clause that would have rewarded him is what names him, and he is made to enter the lodgement himself. FR-18 provides for rewriting *remaining* beat entries on a deviation, and there were none remaining. **The beat sheet is the artefact at fault and the specification has no route to amend it at the last page.**

**D5 — State records were appended out of page order.**
`deltas.jsonl` carries page 7 before page 6, because page 6 was still in retry when page 7 passed. The replay is keyed by page and unaffected, but FR-15 requires the record of a page to be appended before the next page begins, and here it was not. Writing pages ahead of their verdicts is what caused it.

**D6 — Context traces were assembled out of order, and all ten were regenerated at close.**
`assemble(N)` is a pure function of the bible and the state log up to page N, so a regenerated trace is byte-identical in content; timestamps are not. Three pages had no trace at all until the close, because their contexts were assembled while an earlier page was still in retry. The regenerated set uses the repaired records for pages 1 and 3, which is what a resumed run would also see. More seriously, the trace for page 5 was first assembled before chapter 1's digest existed, so it lacked a digest the flow requires at a chapter opening (TR-12). No trace was read back as state (TR-06).

**D7 — `control.consistency_gate_max_attempts` was raised mid-run, from 3 to 5.**
Recorded here because the run would otherwise have terminated at A6 with nothing written, and because the closing report is where a superseded or amended control value belongs (FR-37, TR-03c). The raise is the subject of §5.

**D8 — The chapter-1 continuity repair changed a page's flag status.**
Page 1 entered the ledger flagged for FR-10 and left it unflagged, because the repair rewrote it through the ordinary page path and the rewrite happened to land in band. Nothing in the specification forbids this, and nothing in it predicts it. The flag ratio the acceptance criteria test is therefore sensitive to the order in which repairs and page writes interleave.

---

## 8. Open issues touched by this run

| ID | Status after the run |
|---|---|
| OI-05 / TI-05 | **Answerable.** An independent judge doubled the call count as predicted and rejected 8 pages and 4 beat sheets that a self-grading arrangement passed. Recommend closing in favour of independence, with the cost recorded |
| OI-07 / TI-10 | **Still open and now evidenced.** The lexical proxy passed an objective the independent judge identified as a relabelling. Blocking for unattended runs |
| OI-02 / TI-03 | `page.target_words` 350 is tight for the same reason as before, and for a new one: consistency repairs lengthen pages, so the two budgets interact. 380 to 400 would have saved both flagged pages |
| TI-01 | Still open. `model.id` and `model.max_output_tokens` are null, which is why §12 could not be run as built software |
| TI-07 | The digest bound introduced in v2.2 works: three digests at 199, 195 and 191 words against a ceiling of 200, one rejected by the code and rewritten. The previous run's digests averaged four times their budget |
| **new** | `control.max_continuity_repairs` = 2 per run is undersized once the audit is independent. See §6 |
| **new** | Phase A has no flag-and-continue and Phase B does. See §5 |
| **new** | The A6 gate does not distinguish blocking findings from advisory ones. See §5 |
| **new** | `beats.json` cannot be amended when the defect is in the last beat. See D4 |

---

## 9. Inventory produced

```
bible/premise.md, rules.md, characters/ (4), settings/ (4), beats.json
state/deltas.jsonl          12 records for 10 pages (2 superseding repairs, FR-40)
state/chapters/01..03.md    3 digests, 199 / 195 / 191 words
pages/01..10.md             10 pages, frontmatter added by the orchestrator (TR-08)
runs/2026-09-17T08-15/      config.json, context traces
story.md                    the manuscript, rebuilt from pages/ (FR-29)
report.md                   this file
```

**FR-45 verified:** `stories/the-cold-lamp/` was hashed before the first write and after the last. All 83 files are byte-for-byte unchanged. No path resolved outside `derived.story_root` at any point in the run.
