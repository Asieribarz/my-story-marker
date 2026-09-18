# Control panel

A local three-tab UI over `config.json` and the story workspaces. Standard
library only, no dependencies and no build step; the charts are inline SVG.

```
python ui/server.py
```

then open <http://127.0.0.1:8765>. The server binds to localhost.

**Parameters tab.** Every group of `config.json` except `paths` is
editable. A save is validated against the invariants of functional §2.3 before
anything is written: if any invariant fails the file is left untouched and the
violations are listed above the form (`control.abort_on_invalid_config`). When
`chapters` and `pages_per_chapter` disagree the supersession is reported rather
than applied silently (FR-37). `paths` is not editable from the UI: a path
edited by hand is how a run escapes its workspace (FR-45, I-9).

**Dashboard tab.** The derived shape — chapter sizes, act spans, anchor
pages, word band — is computed on each request from the rules of functional
§2.2 and never stored (TR-03b, FR-36). Below it, four figures and a per-page
table, all read from the selected story's own artefacts:

- **Page length against the band.** One dot per page on a scale zoomed to the
  band, with the target and the written mean drawn across it. Dots rather than
  bars: the baseline is not zero, and a bar on a baseline that is not zero
  encodes a length it does not have. The *length bias* tile is the mean over
  the target — both measured runs came in above it, and every length retry was
  a page over the ceiling, so the direction is the finding.
- **Budgets spent.** Retries, continuity repairs and flagged pages against the
  ceilings in `control`. A budget read only in the closing report is a budget
  nobody could act on: one page of `the-seeding-engine` spent the whole run's
  repair capacity in chapter 1, and the audit ran disarmed for three chapters
  afterwards.
- **Structural load.** How many jobs each page carries — turning the story,
  closing a chapter, opening one, crossing an act boundary — beside its retries
  and repairs. Computed from the derivation, never stored.
- **Threads.** Each thread from the page that opens it to the page that closes
  it. A thread minted by a record that a repair later superseded is drawn on
  its own row and named as retired: replay prefers the superseding record
  (TR-04c) but minting is monotonic, so the sequence keeps a hole that a reader
  would otherwise have to reconstruct by hand.

Where a chapter-close repair appended a second record for a page, the later
record stands and the pair is counted under *repairs* (FR-39). A state record
with no word count is reported as uncounted rather than averaged in as a page
of zero words.

**Novel tab.** The written pages, chapter by chapter, read from the workspace
with their front matter.

Each tab is addressable by hash — `#params`, `#dash`, `#novel`.

A page is marked as an anchor from the beat sheet the story was written from,
not from the anchors derived at the current configuration; where a workspace
holds more pages than `config.json` now asks for, the mismatch is reported
rather than counted as progress past 100%.

The server writes only `config.json`. It never writes inside a story workspace.

**Branding.** The tokens at the top of `static/index.html` carry the Qaracter
palette — navy `#233441` as the structural colour, orange `#FF7932` as the
accent, over near-white surfaces — and nothing else hard-codes a colour. The
accent is defined twice on purpose: `--brand` is the interface orange, the brand
value exactly, and `--data-a` is one step darker for chart marks, which have to
clear 3:1 against the surface to be read as a quantity. The two categorical
chart hues were checked for lightness, chroma, colour-vision separation and
contrast; a third category is carried by shape and label, never by a third hue.
Type is Satoshi, loaded from Fontshare and falling back to the system stack when
the panel is offline. `static/qaracter-logo.svg` is the official white wordmark
for the navy header and `static/qaracter-logo-dark.svg` the dark one, used as
the favicon.

## Files

| File | Role |
|---|---|
| `server.py` | HTTP server: `/api/config` (GET, PUT), `/api/progress`, `/api/manuscript` |
| `derive.py` | Derivation (functional §2.2) and validation (§2.3), no I/O beyond loading the config |
| `static/index.html` | The whole front end: markup, styles, script |
| `static/qaracter-logo.svg` | Wordmark, white, for the navy header |
| `static/qaracter-logo-dark.svg` | Wordmark, dark, used as the favicon |
