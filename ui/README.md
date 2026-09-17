# Control panel

A local two-pane UI over `config.json` and the story workspaces. Standard
library only, no dependencies and no build step.

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
§2.2 and never stored (TR-03b, FR-36). Below it, per page: word count against
the band, retries, flags, act, anchor, and the state-record summary, read from
the selected story's own artefacts. Where a chapter-close repair appended a
second record for a page, the later record stands and the pair is counted under
*repairs* (FR-39).

**Novel tab.** The written pages, chapter by chapter, read from the workspace
with their front matter.

Each tab is addressable by hash — `#params`, `#dash`, `#novel`.

A page is marked as an anchor from the beat sheet the story was written from,
not from the anchors derived at the current configuration; where a workspace
holds more pages than `config.json` now asks for, the mismatch is reported
rather than counted as progress past 100%.

The server writes only `config.json`. It never writes inside a story workspace.

**Branding.** `--brand` at the top of `static/index.html` is the single accent
token; nothing else hard-codes an accent colour. `static/qaracter-logo.svg` is a placeholder wordmark — replace the
file, keep the name.

## Files

| File | Role |
|---|---|
| `server.py` | HTTP server: `/api/config` (GET, PUT), `/api/progress`, `/api/manuscript` |
| `derive.py` | Derivation (functional §2.2) and validation (§2.3), no I/O beyond loading the config |
| `static/index.html` | The whole front end: markup, styles, script |
| `static/qaracter-logo.svg` | Placeholder wordmark |
