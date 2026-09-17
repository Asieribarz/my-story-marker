# Execution Report: Marco en Madrid

**Story ID:** marco-en-madrid  
**Config Version:** 2.3  
**Execution Date:** 2026-09-17  
**Status:** Complete

---

## Summary

"Marco en Madrid" is a complete adventure narrative of 8 pages across 3 chapters, following the arc of a Peruvian architect who arrives in Madrid with a signed job contract that turns out to be invalid. The story explores themes of displacement, identity, shame, and acceptance, culminating in Marco's recognition that worth exists independent of career achievement.

---

## Configuration

| Parameter | Value |
|---|---|
| Pages total | 8 |
| Chapters | 3 |
| Pages per chapter | [3, 2, 3] (derivation: largest remainder) |
| Story tone | classic adventure |
| Audience | general reader |
| Language | en (English) |
| Target words per page | 370 ± 20% (296–444) |
| Max characters per page | 3 |
| Max settings per page | 2 |
| Anchor pages | Pages 3, 5, 7 (auto: first, middle, last of development act) |

---

## Structure

### Acts (from `organization.act_proportions`)
- **Setup:** Pages 1–2 (20% of 8 = 1.6 → 2 pages)
- **Development:** Pages 3–7 (60% of 8 = 4.8 → 5 pages)
- **Resolution:** Page 8 (20% of 8 = 1.6 → 2 pages, rounded to 1 to fit 8-page limit)

### Chapters (from `organization.chapters = 3`)
- **Chapter 1 — Arrival:** Pages 1–3
- **Chapter 2 — Survival:** Pages 4–5
- **Chapter 3 — Reckoning:** Pages 6–8

### Anchor pages (turning points)
- **Page 3 (anchor):** Entry into complication. Marco chooses to lie and begins illegal work.
- **Page 5 (anchor):** Central reversal. Marco attempts legality, is rejected, accepts permanent illegality.
- **Page 7 (anchor):** Crisis before resolution. Marco's mother arrives and discovers the truth.

---

## Bible (Fixed state)

**Characters (5 total, within max of 6):**
1. Marco Domínguez — protagonist. Arc: architect seeking validation → human learning to exist without it.
2. Elena Sanz — ally. Arc: offering shelter → witnessing transformation.
3. Miguel Ferrero — antagonist. Arc: dismissive bureaucrat → unwitting mirror.
4. Rosa Domínguez — ally (mother). Arc: proud believer → suspicious → accepting.
5. Javier Ocampo — ally. Arc: Marco's competition → fellow traveler.

**Settings (4 total, within max of 5):**
1. Madrid — the city, indifferent stage
2. Elena's apartment — refuge and mirror
3. Government office — bureaucracy, system made visible
4. Construction site — temporary labor, honest work

**World rules (8 total):**
1. Visa restrictions bind choices.
2. Professional credentials don't transfer.
3. Madrid is a city of invisible hierarchies.
4. Money runs out faster than hope.
5. Family expectations are a form of debt.
6. Displacement creates temporary communities.
7. Work without meaning feels like erasure.
8. True rest requires acceptance.

---

## Execution metrics

| Metric | Target | Actual | Status |
|---|---|---|---|
| Pages written | 8 | 8 | ✓ |
| Mean words per page | 370 | ~410 | Within tolerance |
| Characters in cast | ≤3 per page | Compliant | ✓ |
| Settings per page | ≤2 per page | Compliant | ✓ |
| Anchor pages hit | 3 (pages 3, 5, 7) | 3 | ✓ |
| Chapter balance | ≤1 page variance | [3, 2, 3] — within tolerance | ✓ |
| Continuity audit | Passed | No contradictions in state log | ✓ |

---

## State management

**State log:** deltas.jsonl — 8 records, one per page. Each record contains:
- Page summary
- Updated character state
- Threads opened / closed
- Concrete facts (dates, locations, quantities)

**Chapter digests:** 3 files, one per chapter
- Chapter 1: 185 words
- Chapter 2: 198 words
- Chapter 3: 192 words
(All within `context.chapter_digest_max_words = 200`)

---

## Narrative arc

**Act I — Setup (Pages 1–2)**
Marco's arrival with hope, the job's dissolution, the pivot to survival.

**Act II — Development (Pages 3–7)**
- *Page 3 (anchor):* Marco enters the complication via the lie and undeclared work.
- *Pages 4–6:* Settlement into illegal economy, network formation, integration.
- *Page 5 (anchor):* Central reversal—bureaucratic rejection ends belief in legal solutions.
- *Page 6–7:* Family confrontation, acceptance, visibility among those who matter.
- *Page 7 (anchor):* Crisis—mother discovers truth, reckoning follows.

**Act III — Resolution (Page 8)**
Marco accepts his invisibility to official structures and visibility to community. Builds something real in the gap between official and actual.

---

## Key facts (fact ledger)

| Fact | Page(s) | Value |
|---|---|---|
| Arrival date | 1 | Day 1 in Madrid, via Barajas |
| Firm closure | 2 | 2 weeks before arrival |
| Job loss discovery | 2 | Day 2 in Madrid |
| First construction work | 3 | Day 3+ |
| Move to basement | 3–4 | ~Week 2 |
| Immigration appointment | 5 | 3 months after arrival |
| Deportation notice | 5 | Issued at 3 months |
| Mother's arrival | 7 | ~Month 6 |
| Truth disclosure | 7–8 | Week of mother's visit |
| Community kitchen project | 8 | Post-acceptance, ongoing |

---

## Quality checks

### Consistency (K-series)
- **K1–K3 (characterization):** Each character remains consistent in voice, arc, and motivation.
- **K4–K5 (plot coherence):** Each beat advances the story toward resolution.
- **K6–K7 (setting/continuity):** Locations are consistent; Marco's progression through physical spaces mirrors emotional arc.

### Technical requirements
- **Derivation rules:** Chapter sizes, acts, anchor pages derived and verified ✓
- **Workspace boundary:** All files written to `stories/marco-en-madrid/`, no escape ✓
- **No literals in prompts:** All configuration values sourced from `config.json` ✓
- **State log integrity:** Append-only, all pages recorded ✓

---

## Narrative quality

The story **does not** attempt to be a formal architecture treatise or a how-to on immigration law. Instead, it uses Marco's arc to explore how identity, worth, and belonging operate when systems reject you. The turning points are psychological and social, not circumstantial:

- Page 3: Marco chooses the lie (agency within constraint)
- Page 5: Marco accepts the system's rejection (shifts from resistance to adaptation)
- Page 7: Marco's mother witnesses him and accepts him (external validation becomes less necessary)
- Page 8: Marco builds something true (worth expressed independently)

The story's climax is not dramatic action but recognition: Marco becomes visible to his mother and himself. The resolution is not a return to the original plan but a new stability built on honesty and community.

---

## Outputs

| Artefact | Location | Status |
|---|---|---|
| Premise expansion | bible/premise.md | ✓ |
| World rules | bible/rules.md | ✓ |
| Characters (5 files) | bible/characters/*.md | ✓ |
| Settings (4 files) | bible/settings/*.md | ✓ |
| Beat sheet | bible/beats.json | ✓ |
| Pages (8 files) | pages/page_00[1-8].md | ✓ |
| State log | state/deltas.jsonl | ✓ |
| Chapter digests (3 files) | state/chapters/*.md | ✓ |
| Assembled manuscript | story.md | ✓ |
| This report | report.md | ✓ |

---

## Conclusion

"Marco en Madrid" completes all three phases of the orchestration:
- **Phase A** (Preparation): Bible written, cast defined, structure set.
- **Phase B** (Composition): 8 pages written to spec, state logged, consistency maintained.
- **Phase C** (Assembly): Manuscript assembled, report completed.

The story achieves its narrative goal: to show how a person learns to exist without the identity that was supposed to define them, and how that loss becomes, paradoxically, the foundation of something more real.

**Story ready for reading.**
