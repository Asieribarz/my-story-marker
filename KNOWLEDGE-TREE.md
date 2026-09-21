# Knowledge tree

A map of this repository: where each kind of knowledge lives, what governs what, and which
identifier namespace to search when you have a question.

**This file states no rule.** It holds no configuration value, no requirement text, no
behaviour. Every node is a pointer to the one place that owns the thing, by file and by
identifier. That is deliberate: `CLAUDE.md` forbids restating spec content in a new file,
because two copies of a rule are two rules. If you find a rule written out here, that is a
defect in this file, not a convenience.

Read it to find where to look. Read the thing itself to know what it says.

---

## 1. The authority spine

When two sources disagree, the higher one wins. This ordering is stated in `CLAUDE.md` and
is the single most useful thing to know about the repository.

```
config.json                          every control and organization value
  └── specs/functional_…             what the system does           FR-01 … FR-49
        └── specs/technical_…        how it does it                 TR-01 … TR-24
              └── specs/self_improvement_…   the loop between runs  SR-01 … SR-17
                    └── .claude/agents/*.md  what each call judges and refuses
                          └── stories/the-cold-lamp/report.md   evidence — never edit
```

Two properties of the spine worth holding in mind:

- **`config.json` is the only place a number lives** (FR-20). A literal anywhere else — a
  spec, an agent file, a prompt, code — is a defect. A run reads this file and never writes
  it.
- **The agent files are the exception to "do not restate".** Behaviour lives there and only
  there; the specs hold the wiring and the inventory and restate none of it.

---

## 2. The three specifications, and the line between them

They are three documents because they describe three different units of work.

| Document | Unit of work | Owns | Identifiers |
|---|---|---|---|
| `specs/functional_specification_story_agent.md` | one run | what the system does, the flow, acceptance | FR, I, OI, V |
| `specs/technical_specification_story_agent.md` | one run | how, file formats, per-call wiring, budget | TR, TI |
| `specs/self_improvement_specification_story_agent.md` | **between** runs | the calibration loop | SR, SI, SV |

The third is separate precisely because nothing in the other two crosses a run boundary —
story isolation (FR-42, FR-45) exists so that nothing does. The calibration loop is the
first mechanism that carries anything from one story to the next, and burying that inside a
document scoped to a single run would hide the property most in need of review.

### Where to look inside each

**Functional** — §2 configuration and derivation · §4 state model · §5 the flow, with §5.0
assigning every step to code or to a named agent · §7 the FR table · §9 acceptance criteria
· §11 change control, §11.5 open issues.

**Technical** — §2 architecture · §4 file layout and formats · §5 per-call contracts, wiring
only · §6 `assemble(N)` · §7 budget · §8 validation · §9 resume · §10 traceability · §11
open issues · §12 build inventory.

**Self-improvement** — §1.3 the five controls that replace a human reviewer · §2 the metric,
the bias and the guards · §4 learned state · §5 the loop, its validation checks C-1…C-7 and
its termination conditions · §7 the SR table · §9.5 open issues.

---

## 3. The six call types

Each is one file, and **that file is where its behaviour is defined.** To change how a call
behaves, change the agent file. To change what it is handed or what it returns, change the
agent file *and* technical §5.

```
.claude/agents/
├── bible-builder.md        Phase A, one invocation    writes paths.staging_dir only
├── page-writer.md          one per page + retries     writes nothing
│     └── rule 2, between <!-- calibrated:length --> markers
│         the ONLY bytes in this tree the calibration loop may rewrite
├── consistency-checker.md  one per page attempt       writes nothing   K1 … K7
├── continuity-auditor.md   one per chapter close      writes nothing
├── closing-auditor.md      once, Phase C              writes nothing
└── length-calibrator.md    between runs, step L6      writes nothing
```

**Two calls have no agent file and never will.** The state-record extraction and the chapter
digest are owned by the orchestrator. They carry no narrative authority, and giving either
an agent file would imply it did (technical §5).

**Two rules about these six that are load-bearing:**

- `page-writer` and `consistency-checker` are never merged into one invocation (TR-09,
  TR-09b). That separation is what retires the principal risk of version 1.x.
- No agent writes anything but the staged bible (FR-49). The orchestrator commits at A7 and
  owns every other file in the workspace.

---

## 4. The flow

Functional §5 is the authority; §5.0 is the table that says who performs each step. The
shape:

```
Phase A — once per run, atomic
   A0  load · derive · validate            code
   A1–A5  the bible                        bible-builder, ONE invocation
   A6  the gate      ├── arithmetic half   code
                     └── anchor reversal   a delegated call with no agent file — OI-12
   A7  commit the staged bible             code

Phase B — once per page
   B0–B2  beat · sheets · assemble(N)      code
   B3  write the page                      page-writer
   B4  mechanical validation               code
   B5  consistency, separate invocation    consistency-checker
   B6  retry or flag                       code
   B7  page file + state record            code, with one extraction call
   B9  continuity audit, at chapter close  continuity-auditor
   B10 repair                              back through B3–B7
   B11 chapter digest                      one orchestrator call, bounded in code

Phase C — once
   C1–C3  thread replay · arcs · balance   code
   C4  assemble the manuscript             code
   C5  the closing report                  closing-auditor, over numbers it never recomputes
```

**The dividing line that matters.** Anything asserted rather than executed carries no
evidence. Config validation and derivation, the A6 arithmetic, page length, the roster
check, `assemble(N)`, thread and arc replay, chapter balance and manuscript assembly are
code. Everything else is judgement, and judgement is delegated and labelled.

---

## 5. State: four kinds, and the distinction is the point

| Kind | Where | Property |
|---|---|---|
| Fixed | `bible/` | written once at A7, immutable thereafter |
| Mutable | `state/deltas.jsonl` | append-only; a repair supersedes rather than overwrites |
| Derived | nowhere | computed from `config.json` at load; storing it is the defect it exists to remove (TR-03b) |
| Learned | `state/calibration.json` | measured from what previous runs produced |

Two things are **projections, not files**: the thread register (functional §4.2) and the
calibration ledger (self-improvement §4.3). Both are obtained by replay. A ledger held as a
shared file is a value two runs could disagree about.

Neither a derived nor a learned value may be written into `config.json`.

---

## 6. What is on disk

```
config.json                     shared, read by every run, written by none
CLAUDE.md                       the working rules; read this before changing anything
KNOWLEDGE-TREE.md               this map
specs/                          the three specifications
.claude/agents/                 the six call definitions
calibration/                    the loop, built and tested
tests/test_calibration.py
loops/                          RUNBOOK.md, and one rendered report per wording tried
tools/                          orchestrator parts written to run campaign-02 by hand
ui/                             derive.py — derivation and the invariants of functional §2.3
stories/<story-id>/             one workspace per novel; nothing above it is writable
  bible/  state/  pages/  runs/  story.md  report.md
```

**Every path in `paths` except `stories_root` resolves inside the current story's
workspace** (FR-42, FR-45, I-9). A path that is absolute, or that climbs above
`derived.story_root`, is rejected before the first write. One story overwriting another is
the defect this layout exists to remove, and it was silent when it happened.

---

## 7. Code: what exists, what does not

| | Status |
|---|---|
| `calibration/` + its tests, driven by `loops/RUNBOOK.md` | **Built.** The only code the specs planned that exists |
| `ui/derive.py` | **Built.** Derivation and validation |
| `tools/` — A6 gate, sheet format, `assemble(N)`, validation, state, audits, manuscript | **Built ad hoc.** Working parts, *not* the inventory of technical §12 |
| 16 orchestrator modules and 8 test modules of technical §12.3–12.5 | **To build.** `run.py` does not exist |

**The orchestrator is a session, not a program.** Every run to date was orchestrated by
hand. `tools/` was written during campaign-02 to execute the steps §5.0 assigns to code, so
that they would be measured rather than asserted; it is not the same thing as the build
inventory, and treating it as such would leave §12 looking half-done when it has not been
started.

---

## 8. Identifier namespaces — which prefix answers which question

| Prefix | Question it answers | Range | Lives in |
|---|---|---|---|
| `FR-` | what must the system do | 01–49 | functional §7 |
| `TR-` | how is it built | 01–24, with letter variants | technical, throughout |
| `SR-` | what must the calibration loop do | 01–17 | self-improvement §7 |
| `I-` | what makes a configuration invalid | 1–9 | technical §2, functional §2.3 |
| `K` | the seven consistency checks | 1–7 | `consistency-checker.md` |
| `C-` | validation of a candidate wording | 1–7 | self-improvement §5.4 |
| `OI-` | known functional defect, open | 01–12 | functional §11.5 |
| `TI-` | known technical defect, open | 01–17 | technical §11 |
| `SI-` | known loop defect, open | 01–06 | self-improvement §9.5 |
| `V-` | pre-commit checklist, functional | 01–14 | functional §11 |
| `SV-` | pre-commit checklist, the loop | 01–09 | self-improvement §9.3 |

If you are hunting a rule and do not know where it lives, the prefix tells you the file.

---

## 9. The open issues, clustered by what they block

Thirty-five open issues is too many to hold in the head. They fall into five groups.

**Blocking approval.** TI-01 — `model.id` and `model.max_output_tokens` are null, so the
cost of a run is unknown. SI-04 — the review roles of the self-improvement spec are
unassigned.

**Blocking any unattended run.** OI-07 / TI-10 — the anchor-reversal gate is a proxy and its
failure mode is silent. The campaign-02 run measured a second mode: the gate returned
opposite verdicts on byte-identical input, and the unsafe verdict was the pass. See the run
log under `stories/the-glass-ferry/runs/`.

**Introduced by the delegated form.** OI-10 / TI-14 — an agent definition cannot carry a
temperature, so TR-10 has no mechanism. OI-11 / TI-15 — it cannot carry an empty tool
allowlist, so the FR-08 ceilings rest on instruction for the two most frequent call types.

**Properties of the loop, not bugs in it.** SI-05 — the search over wordings has no
convergence argument; a text is not contractive the way a scalar was. SI-06 — a wording is
judged on one run, which is a small sample of a noisy quantity.

**Live and confirmed by measurement.** SI-01 — the `Length` section of the payload must
carry the band and no instruction, or the loop measures a rewritten rule against an
un-rewritten copy. SI-02 — the criterion was already met at the starting wording, so the
loop terminates on entry; campaign-02 confirmed this, converging after one observation with
`length-calibrator` never invoked.

---

## 10. The evidence base

The project's claims about itself rest on runs, not on assertions. Where to find them:

| Workspace | What it is |
|---|---|
| `stories/the-cold-lamp/` | the run of 2026-09-15 under specs v2.1. **`report.md` is never edited** — rewriting it destroys the only measurement the project has |
| `stories/the-seeding-engine/`, `stories/the-salt-road/`, `stories/marco-en-madrid/`, `stories/ignacio-and-the-sirens/` | earlier hand-orchestrated runs |
| `stories/ascensor-loco/`, `stories/loro-mudo/` | calibration pilots. **Read the warning below before citing either** |
| `stories/the-glass-ferry/` | campaign-02 iteration 1, the first run under the delegated form of v2.4 |
| `loops/summary.md`, `loops/v1.md` | renderings of the observations; rebuildable, never a source of truth (SR-13) |

**Run artefacts are dated by the specs they were produced under.** The artefacts of
`the-cold-lamp` were produced under config v2.0; derivation reproduces the same shape at the
current settings, so they remain consistent, but they were not generated by the current
specs.

### The two pilots carry observations that no prose backs

`ascensor-loco` and `loro-mudo` each hold a `state/calibration.json` recording 8 pages, 0
first-attempt length failures and a rate of 0.000, and an `attempts.jsonl` with 8 word
counts. **Neither workspace contains a single page file, a state log or a manuscript.**
`loro-mudo` additionally still holds an uncommitted `runs/staging/`, which means its Phase A
never reached A7.

The consequence is specific and it matters, because these are two of the three flows
`loops/v1.md` averages: their word counts cannot be checked against any prose, so their
contribution to the mean rate of variant `v1` is unverifiable. They are excluded from the
campaign-02 ledger — their `epoch` carries no `epoch_label` at all — but the per-variant
report averages across epochs and includes them.

Treat the pilots as a record that a measurement was taken, not as evidence about page
lengths. The one flow under `v1` whose rate can be checked against its own pages is
`the-glass-ferry`.

---

## 11. Before you change anything

The procedure is functional §11.4, and it is not optional. A change to the specs is not
finished until it is recorded in §11.5 or §11 open issues, versioned in the version-history
table, and re-checked against V-01 to V-10.

The checks that catch what review misses are listed in `CLAUDE.md` under *Checks before
committing a spec change* — every `group.key` referenced exists in `config.json` and no
config key is unreferenced, every FR referenced is defined and vice versa, every Mermaid
edge names a declared node, no stale parameter names, every call type in technical §5 has
exactly one file in `.claude/agents/` and no file there is unreferenced, no agent definition
contains a configuration literal, and every step of functional §5 appears in §5.0.

Work on a branch, not `main`.
