# Execution Report: The Hair-Rope

**Story ID:** ignacio-and-the-sirens
**Config version:** 2.3
**Execution date:** 2026-09-17
**Run:** `runs/2026-09-17T11-00/`
**Status:** Complete

---

## Summary

A complete adventure of 10 pages in 3 chapters. Ignacio Robles, a Cadiz privateer, has spent
eleven years trying to prove that mermaids exist, because one held him out of the water for a
night and a day when he was twenty. He takes one alive, recognises the healed tear on her
forearm, and finds that the proof and the debt cannot both be paid. He cuts the rope.

## Configuration as run

| Parameter | Value | Source |
|---|---|---|
| `organization.pages_total` | 10 | config |
| `organization.chapters` | 3 | **see deviation D-1** |
| `organization.act_proportions` | 0.20 / 0.60 / 0.20 | config |
| `organization.anchor_pages` | `"auto"` | config |
| `page.target_words` | 380 | config |
| `page.length_tolerance` | 0.20 → band 304–456 | config |
| `context.max_characters_per_page` | 3 | config |
| `context.max_settings_per_page` | 2 | config |
| `context.verbatim_summary_window` | 8 | config |
| `context.chapter_digest_max_words` | 200 | config |
| `bible.max_characters` / `max_settings` | 6 / 5 | config |
| `control.max_retries_per_page` | 2 | config |
| `control.max_continuity_repairs` | 2 | config |

### D-1 — deviation from the working-tree config

The working tree carried `organization.chapters: 34` against `organization.pages_total: 10`.
That fails invariant 1 of functional §2.3 (the derived chapter count must lie in
`[1, pages_total]`), and with `control.abort_on_invalid_config` the run does not start. The run
was made against the last committed value, `3`. **`config.json` was not modified**: a run reads
the configuration and never writes it (§3.1). The invalid value is still in the working tree and
is the operator's to resolve.

## Derived shape (functional §2.2)

- **Chapter sizes** — `10 mod 3 = 1`, so the first chapter takes one page more: **4 / 3 / 3**.
  Chapter 1 pages 1–4, chapter 2 pages 5–7, chapter 3 pages 8–10.
- **Acts** — largest remainder over 10 pages: setup 2, development 6, resolution 2.
  Setup 1–2, development 3–8, resolution 9–10.
- **Anchors** — first, middle and last page of the development act: **3, 5, 8**.

| Anchor | Reversal |
|---|---|
| 3 | Pau feels the song in the bone. The voyage stops being an argument about whether she exists and becomes a hunt that cannot be called off. |
| 5 | The catch succeeds and the tear on her forearm identifies her. The hunter becomes the jailer of his own creditor. |
| 8 | At the bar Ignacio hands the bond back intact and turns the ship. He stops trying to be believed. |

## Bible

- **World rules:** 7 (bounds 4–8). r1 shallow ground, r2 felt in the bone, r3 the voice spends at
  a fixed rate, r4 no two witnesses ever agree, r5 hair-rope holds, r6 return a year to the day,
  r7 nothing crosses the river bar alive.
- **Characters:** 5 of a maximum 6 — Ignacio Robles (protagonist), Brites Olaya (ally),
  Yara of the Restinga (antagonist), Don Fausto Delgado (antagonist), Pau (ally).
- **Settings:** 5 of a maximum 5 — La Alondra, the Restinga, Cadiz harbour, the tank, the bar.
- **Beats:** 10 entries, one per page; no page exceeds 3 characters or 2 settings.

## Measurements

| Metric | Value |
|---|---|
| Pages written | 10 / 10 |
| Manuscript length | 4 078 words of page text |
| Mean page | 407.8 words (band 304–456) |
| Shortest / longest page | 358 (p1) / 445 (p10) |
| Pages outside the band | 0 |
| Retries | 0 |
| Flagged pages | 0 (ceiling `control.max_flagged_ratio` = 1 page) |
| Threads opened / closed | 6 / 6 |
| Chapter digests | 3, at 199 / 195 / 194 words (bound 200) |
| Continuity repairs | 1 of 2 permitted |

### Digest bound

All three digests overran `context.chapter_digest_max_words` on the first pass (243 / 231 / 279)
and needed two compression passes. This is TI-07 showing up on a second story: the bound is tight
enough that it is the routine failure, not the exception.

### Continuity repair R-1 (FR-39)

The fact ledger did not close on the bond term. Page 1 fixes it at sixty-one days; page 8 carried
fifty-three days remaining at the bar, and page 10 a forfeit by twenty-one days on arrival — two
counts that cannot follow from the same voyage. Resolved to: seventeen days at the bar, a
fortnight becalmed off Trafalgar on the passage home, and arrival seven days past the bond. Pages
08 and 10, digest 03 and the affected fact records were amended, with a `supersedes` record
appended to `state/deltas.jsonl`.

### Bible repair, Phase A

World rule r3 was first written as "loses her voice within one turn of the half-hour glass",
which no beat after page 5 could satisfy — the captivity runs six days. It was rewritten before
page 6 as a steady rate counted in turns, which keeps the glass as the story's clock and lets the
arc reach page 9. The premise expansion was amended to match.

## Honest limits of this run

1. **The consistency and continuity passes were judgement by the same model that wrote the
   pages.** TR-09 requires a separate call; a separate *pass* was run, not an independent
   endpoint. This is exactly the defect recorded against the run of 2026-09-15, and it is not
   fixed here. Do not read the zero-retry, zero-flag numbers as independently verified.
2. **The A6 anchor-reversal check is the same lexical proxy** (OI-07 / TI-10). The three anchor
   objectives were read for a change of direction by eye.
3. **Length, roster, chapter balance, thread replay, digest bound and manuscript assembly were
   executed as code**, not asserted. Those numbers are trustworthy.
4. **Cost is unknown** (TI-01): `model.id` and `model.max_output_tokens` remain `null`.
