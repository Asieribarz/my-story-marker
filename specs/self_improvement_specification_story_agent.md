# Self-improvement specification
## Adventure story generator agent — calibration of the length instruction

| | |
|---|---|
| **Version** | 2.0 |
| **Date** | 18 September 2026 |
| **Governs** | One quantity: the wording of the length instruction in `page-writer.md` |
| **Depends on** | Functional specification v2.4, technical specification v2.4, `config.json` |
| **Status** | Draft for review |

---

## 1. Scope

This document specifies a loop that runs **between** runs. Each run writes what it measured about its
own page lengths; when that measurement is worse than the criterion, the length instruction handed to
the writing call is rewritten and the next run is written under the new wording. The loop is bounded,
it stops on a measured criterion, and it stops unconditionally after a fixed number of runs whether or
not that criterion is ever met.

It is a third document rather than a section of the other two because it describes a different unit of
work. The functional and technical specifications describe **one run**, from a premise to a manuscript.
Nothing in them crosses a run boundary, and the isolation of a story workspace (FR-42, FR-45) exists
precisely so that nothing does. This loop is the first mechanism that carries anything from one story
to the next, and putting it inside a document whose every requirement is scoped to a single run would
hide the one property most in need of review.

**One run is one iteration.** A story is written from beginning to end under one wording, measured, and
only then may the wording change. Nothing is rewritten part-way through a run: the pages of one story
are not comparable to each other — page one is written with no digest, no summaries and no bridge,
page ten with all three — so a wording judged on the first half of a story and a wording judged on the
second half would differ by position as much as by phrasing, and the loop could not tell which.

### 1.1 What is calibrated

One thing: **the wording of rule 2 of `.claude/agents/page-writer.md`**, the instruction that tells the
writing call what to do with the word count it is given. Not the target, not the band, not the beat
sheet, not any other rule of that file, not any other agent definition.

The block is delimited in the file, and the delimiters are what bound the loop:

```markdown
2. <!-- calibrated:length v1 -->
   **Write to the target length, not past it.** Aim at the target and stop.
   <!-- /calibrated -->
```

The choice of this quantity is not arbitrary. Of everything handed to the writing call, length is the
one failure with measured evidence across workspaces, the one whose failures fall in a single
direction, and the one whose correction can be judged from the system's own output.

**The number is not calibrated, and never was in this version.** `page.target_words` and
`page.length_tolerance` remain the operator's, unchanged by any run. What changes is the sentence that
tells the writer what to do with them.

### 1.2 What this document does not contain

It restates nothing from the other two specifications. Where a rule already exists it is referenced by
its identifier: the length check is FR-10, mechanical validation in code is FR-25, values reaching an
agent by payload is FR-47, no literal outside `config.json` is FR-20, workspace confinement is FR-45,
and the prohibition on an agent writing is FR-49. All of them continue to hold, and this loop is
constrained by every one of them.

### 1.3 The boundary this loop must not cross

A loop that edits an agent definition is a system rewriting its own instructions. Version 1.0 refused
that outright and calibrated a number instead. This version permits it, and therefore has to say what
stands in the place of the reviewer that the refusal provided. Five things do, and they are the whole
of the argument:

1. **The surface is delimited and tiny.** The loop may replace the text between the markers of 1.1 and
   nothing else in the file. Every other rule, the input contract, the output contract and the
   frontmatter are outside its reach — including the rules the guards of 2.3 depend on, so the loop
   cannot lower the bar it is being measured against.
2. **Every candidate is validated in code before it is written** (5.4), and an invalid candidate stops
   the loop rather than being applied.
3. **The wording that is in force is committed to version control.** A run written under a wording
   that exists only on disk is not reproducible from a commit, which is a worse defect than the one
   this loop is trying to remove.
4. **Every wording tried, and what it measured, is written down** (4.4) and is readable by a person
   without running anything.
5. **The loop is bounded by `learning.max_calibration_runs` runs** and stops whether or not it
   converges (5.5).

**The number still never appears in the file.** Under FR-47 the target and the band arrive in the
invocation payload as values, and rule 5.4 refuses a candidate that carries a digit. This is what
keeps FR-20 true of a prompt the loop is allowed to edit: the rule is in the file, the number never is.

---

## 2. The quantity under optimisation

### 2.1 The metric

**First-attempt length failure rate**, per run:

```
rate = pages whose first attempt failed the FR-10 length check
       ------------------------------------------------------
       pages written in the run
```

Each page counts once, at its first attempt. A page rewritten by a continuity repair (FR-40) counts at
the first attempt of its original write, not of the repair: a repair corrects content and says nothing
about whether the length instruction was understood.

The loop's objective is that this rate not exceed `learning.max_first_attempt_length_failure_rate`.

**Why the first attempt.** A retry already carries the rejection reason, so a page that comes back the
right length on its second attempt proves only that the writer can read a complaint. The first attempt
is the only one that measures the instruction as written, and the only one whose cost the loop can
remove: every retry is a page call that did not need to happen.

**What counts as a length failure.** A first attempt whose word count falls outside the band derived
from `page.target_words` and `page.length_tolerance`, whether the validation recorded the rejection or
the count simply fell outside. Both are the same event, and reading it from the count as well as from
the rejection makes the metric computable from a run whose validation was not fully logged.

### 2.2 The rate is the trigger, and the bias is a diagnostic

The rate is what the loop acts on: above the ceiling, the wording is rewritten; at or below it, the
loop stops.

The **bias** — mean words written over pages that carry a count, divided by `page.target_words` — is
recorded in every observation and in every report, and triggers nothing. It is there because the rate
saturates: once the band is wide enough to absorb the overshoot, the rate is zero while the
distribution still sits hard against one edge, and a reader looking only at the rate cannot see that a
future tightening of the tolerance would bring the retries straight back. The bias is how a person
sees that coming. It is not a control signal in this version, and the loop never computes a correction
from it.

### 2.3 The guards

Two quantities are measured, reported, and **never optimised**: the share of pages whose first attempt
was rejected by a consistency check (K1 to K7), and the number of continuity repairs the run performed.

They exist because a wording can damage what a number could not. A rule that said to hit the word
count and let nothing else matter would drive the rate to zero and wreck the prose, and an optimiser
told to minimise the rate would find it. The guards are how a reader sees that happen. A wording whose
rate improved while a guard worsened has not improved anything, and 5.5 requires that outcome to be
reported rather than read as success.

They are not folded into the metric: they are judgements about content, they are not caused by the
length instruction, and one number combining them would produce a loop that rewrote the length rule
because a character spoke out of voice.

---

## 3. Configuration

Every value this loop uses is an authoritative input in `config.json`, in a group of its own. This
document names them by path and states no literal (FR-20).

| Path | Governs |
|---|---|
| `learning.enabled` | Whether calibration runs at all |
| `learning.max_first_attempt_length_failure_rate` | The ceiling of 2.1, and the stopping criterion |
| `learning.max_calibration_runs` | The iteration cap, per epoch (4.5) |
| `learning.min_pages_per_observation` | The shortest run that may contribute an observation |
| `learning.max_length_block_words` | The ceiling on the size of the calibrated block (5.4) |
| `learning.epoch_label` | The operator's name for the current campaign (4.5) |
| `paths.loops_dir` | Where the reports of 4.4 are rendered |

**Invariants.** The configuration is invalid, and the run does not start, unless
`learning.max_first_attempt_length_failure_rate` lies in `(0, 1)`, `learning.max_calibration_runs`,
`learning.min_pages_per_observation` and `learning.max_length_block_words` are each at least 1, and
`learning.epoch_label` is a non-empty string. These extend the list in functional specification §2.3
and are checked on the same path, before the first model call (FR-21).

---

## 4. Learned state

The functional specification holds three kinds of state: fixed, mutable and derived (§4.1 to §4.3).
This loop introduces a fourth, and the distinction matters. A **derived** value is computed from the
configuration and is a function of it alone. A **learned** value is measured from what previous runs
produced, and is therefore a function of the system's own behaviour.

Neither may be written into `config.json`. A derived value stored there goes stale; a learned value
stored there would let the system edit the operator's own input, which is the one file a run reads and
never writes.

### 4.1 The calibration observation

One record per run, written at `paths.calibration` inside that run's own workspace:

| Field | Meaning |
|---|---|
| `epoch` | the target, the tolerance, the epoch label, and the variant and digest of the wording in force |
| `asked` | the target the `Length` section carried |
| `band` | the accepted band the FR-10 check used |
| `pages` | pages written, each counted once |
| `first_attempt_length_failures` | the numerator of 2.1 |
| `length_failure_pages` | which pages they were, so a reader can go and look |
| `rate` | as defined in 2.1 |
| `mean_words`, `bias` | the diagnostic of 2.2 |
| `first_attempt_consistency_rejections`, `continuity_repairs` | the guards of 2.3 |
| `instruction` | the wording that produced this run, in full |

A state record with no word count is not a page of zero words: it is a page whose length was never
logged. It is excluded from `mean_words` and named in the observation, never averaged in.

### 4.2 The per-attempt record

The metric of 2.1 requires what the state record of functional §4.2 does not carry: **what each
attempt was rejected for**. From `retries: 2` it is impossible to tell whether the first attempt was
too long, contradicted a world rule, or gave a character the wrong arithmetic.

One record per page attempt is therefore appended while the run is orchestrated, at
`<run directory>/attempts.jsonl`:

```json
{"page": 7, "attempt": 1, "words": 412, "rejected_by": ["length"]}
```

`rejected_by` is empty when the attempt was accepted, and otherwise names the mechanical check
(`length`, `roster`, `structure`) or the consistency checks (`K1` to `K7`) that rejected it. It is
appended by the same code that performs the validation, never typed from memory: what the loop
measures must be what the validation decided.

The run directory is write-only as state (TR-06). These records are read by the loop, which runs
between runs and not during one, so nothing in a run ever reads them back.

### 4.3 The ledger is a projection, not a file

The **calibration ledger** is obtained by reading the observation of every workspace under
`paths.stories_root` and keeping those whose epoch matches the current configuration. Nothing writes
it.

This mirrors the thread register of functional §4.2, which is likewise a replay projection rather than
a stored file, and for the same reason: a ledger held as a shared file would be a value two runs could
disagree about. A run writes one observation, inside its own workspace, and touches no other (FR-45).
Reading across workspaces is permitted; writing across them is not, and that asymmetry is what keeps
this loop compatible with story isolation.

### 4.4 The loop reports

`paths.loops_dir` holds one Markdown file per wording tried, and a summary across all of them. It sits
beside `paths.stories_root` at the repository root and is the only path in the file besides that one
which is not resolved against a story workspace.

That is deliberate and it is bounded: what is written there is a **rendering**, rebuilt from the
observations held in the workspaces, never a source of truth. Deleting the folder and rebuilding it
must reproduce it exactly. The relationship is the one the manuscript has to `pages/`: derived,
rebuilt, never edited in place (FR-29).

Each variant's file carries the wording that was in force, every run written under it with its pages,
failures, rate and bias, the verdict against the ceiling, and the guards. The summary carries every
variant in order with its mean rate, so that the whole campaign is one table.

### 4.5 The epoch, and why the cap needs one

The iteration cap counts observations **in the current epoch only**. The epoch is the target, the
tolerance, the wording in force, and `learning.epoch_label`.

When an operator edits `page.target_words` or `page.length_tolerance`, every earlier observation
describes a system that no longer exists. When the loop rewrites the instruction, the same is true and
more strongly: the ledger for the new wording is empty by construction, which is what makes each
variant's measurement its own.

`learning.epoch_label` is what lets an operator declare a fresh campaign without deleting a
measurement. Observations of an earlier campaign stay on disk, stay readable, and fall out of the
ledger by name rather than by deletion — reported as excluded, with the reason (SR-10). Without it,
re-arming the loop after it converged would mean destroying the evidence that it converged.

---

## 5. The loop

### 5.1 One iteration

| Step | Performed by | Action |
|---|---|---|
| **L0** | code | Read the wording in force and the ledger for the current epoch. If the loop is stopped by 5.5, say which condition and do nothing further |
| **L1** | orchestrator | Write one complete story from the next premise, in its own workspace, under the wording in force. The orchestration is unchanged: the phases, the agents and the per-page loop are exactly those of functional §5 |
| **L2** | code | Append one record per page attempt as validation decides it (4.2) |
| **L3** | code | Compute the observation and write it into that workspace (4.1) |
| **L4** | code | Render the reports (4.4) |
| **L5** | code | Compare the rate against `learning.max_first_attempt_length_failure_rate`. At or below: stop, converged. Above: continue |
| **L6** | `length-calibrator` | One delegation: given the wording in force, the measurement, and every wording already tried, return a candidate wording and nothing else |
| **L7** | code | Validate the candidate (5.4). Valid: replace the block, bump the variant, and go to L1 with the next premise. Invalid: stop and report |

**L1 is the only step that is not arithmetic, and L6 is the only judgement the loop itself makes.**
Everything else is counting, comparison and file writing, and is executed rather than asserted — which
is the same division the rest of the system is built on (technical §2). A loop whose own numbers were
reported by a model would be evidence about nothing.

### 5.2 The criterion

The loop is trying to reach a run whose rate is at or below
`learning.max_first_attempt_length_failure_rate`. That is the whole of the objective. The bias, the
guards and the mean word count are reported at every step and decide nothing.

### 5.3 What the loop may never change

The wording between the markers, and nothing else. Not the band, not `config.json`, not the beat
sheet, not a character sheet, not any other rule of `page-writer.md`, not any other agent definition,
not the payload, and not the orchestration. A change to the set of things this loop may touch is a
change to this document, reviewed under §9.

### 5.4 Validation of a candidate

Checked in code, with no model call, before the candidate is written. Any failure stops the loop; a
candidate is never partially applied.

| # | Check | The failure it prevents |
|---|---|---|
| C-1 | The candidate is not empty | A deleted instruction is the trivial way to stop failing a check about an instruction |
| C-2 | The candidate contains no digit | A configuration literal in an agent definition (FR-20, V-13). A number in a prompt reads as helpful, which is why this is the easiest rule here to break |
| C-3 | The candidate contains no template placeholder | An agent definition is not rendered; values arrive by payload (FR-47) |
| C-4 | The candidate still refers to length | A rule that no longer mentions length is not a length rule |
| C-5 | The candidate is within `learning.max_length_block_words` | The writer's definition heads every page payload as a cacheable prefix (TR-13); an unbounded block raises the cost of every call in every run |
| C-6 | The candidate carries no markers of its own | A nested block cannot be replaced again |
| C-7 | The candidate differs from the wording in force | A loop that re-applies the wording it just measured is not iterating |

### 5.5 Termination

The loop stops, and the wording in force stays as it is, when any of these holds:

1. `learning.enabled` is false;
2. the ledger for the current epoch holds `learning.max_calibration_runs` observations;
3. the most recent observation shows a rate at or below
   `learning.max_first_attempt_length_failure_rate`;
4. the candidate returned at L6 fails any check of 5.4.

Condition 2 is the fixed bound. It is checked before condition 3, it does not depend on the
measurement converging, and it is the reason this loop cannot run forever. Reaching it without
satisfying condition 3 is a legitimate outcome, not an error — and it must be **reported**, never
silent, in the manner of a superseded configuration value (FR-37). A loop that quietly gave up would
leave the operator believing a calibration was still in progress.

A stop under condition 3 whose guards worsened against the first run of the campaign is reported as a
**qualified** convergence, naming which guard moved and by how much. The loop still stops; what it
must not do is call that outcome a clean success.

### 5.6 What is reported

At every step, and in the reports of 4.4: the wording in force, the rate against the ceiling, the
bias, the guards, the position in the campaign, and the condition of 5.5 that currently holds.

This is not decoration. A run under calibration is **not reproducible from `config.json` alone**: two
runs at one configuration can be written under different wordings, because the second ran after the
first was measured. That is an acceptable cost of a loop that learns, but only if every run records
which wording produced it — which is what the `epoch` of the observation is for, and why the wording
itself is copied into the observation in full.

---

## 6. The metric command

A command that answers, from the artefacts on disk and with no model call: **what is the rate, which
wording produced it, and where is the campaign.**

```
python -m calibration.cli status
python -m calibration.cli record  <story> --run <dir> --page N --attempt N --words N --rejected ...
python -m calibration.cli measure <story> --attempts <file>
python -m calibration.cli report
python -m calibration.cli apply   --instruction <file>
```

| Output | Source |
|---|---|
| The wording in force, its variant and digest, and the band | `page-writer.md` and `config.json` |
| Per workspace: pages, first-attempt length failures, rate, mean words, bias, guards | that workspace's observation (4.1) |
| Across the campaign: every variant in order with its runs and mean rate | the ledger projection (4.3) |
| The position in the campaign and which condition of 5.5 holds | the ledger and `config.json` |
| Any workspace excluded from the ledger, named, with the reason | comparison of `epoch` against `config.json` |

The command recomputes nothing a model decided; it reads records and reports them. Where a workspace
predates this specification and has no observation, the command reports what that workspace **can**
still support and states that the rate is unavailable for it.

---

## 7. Requirements

| ID | Requirement |
|---|---|
| SR-01 | The system shall record, per page attempt, whether that attempt was rejected and by which check, at `<run directory>/attempts.jsonl`, so that the metric of 2.1 is computable from artefacts on disk. |
| SR-02 | On closing a run that wrote at least `learning.min_pages_per_observation` pages, the system shall write the calibration observation of 4.1 to `paths.calibration`. A shorter run shall be reported but shall contribute no observation. |
| SR-03 | The calibration ledger shall be obtained by reading the observation of each workspace under `paths.stories_root` and retaining those whose epoch matches the current configuration. It shall not be stored. |
| SR-04 | The calibrated block shall be delimited in `page-writer.md`, and the loop shall replace the text between the delimiters and no other byte of that file or of any other agent definition. |
| SR-05 | No run shall write `config.json`, and no learned value shall be stored in it. |
| SR-06 | Calibration shall stop under any condition of 5.5, and condition 2 shall be evaluated before condition 3. |
| SR-07 | Reaching `learning.max_calibration_runs` without satisfying the measured criterion shall be reported as an unconverged termination, with every wording tried and its rate, and the system shall continue to write stories under the wording in force. |
| SR-08 | Every observation shall record the wording that produced it, in full, and the variant and digest of that wording. |
| SR-09 | A candidate wording shall be validated by the checks of 5.4 in code before it is written, and a candidate that fails any of them shall stop the loop rather than be applied. |
| SR-10 | The command of §6 shall report the metric without invoking a model, and shall name any workspace it excluded from the ledger and why. |
| SR-11 | A page whose record carries no word count shall be excluded from `mean_words` and named, and shall never be averaged in as a page of zero words. |
| SR-12 | Steps L0 and L2 to L5 and L7 shall be executed in code with no delegation; only L1 and L6 are delegated. |
| SR-13 | The reports of 4.4 shall be a rendering of the observations, rebuildable from them exactly, and shall never be read as state. |
| SR-14 | The wording in force shall be committed to version control before the run that uses it is begun. |
| SR-15 | The guards of 2.3 shall be recorded in every observation and reported in every report, and shall never enter the metric of 2.1. A convergence whose guards worsened shall be reported as qualified (5.5). |
| SR-16 | One run shall be written under exactly one wording. No wording shall change part-way through a run. |
| SR-17 | Each iteration shall be written into its own story workspace, from its own premise. |

---

## 8. Dependencies

### 8.1 The payload must not restate the rule

The `Length` section of the assembled context has carried both the numbers and an exhortation —
the target, the band, and a sentence repeating what rule 2 already says. While it does, the loop is
measuring a rewritten rule with an un-rewritten copy of the old one arriving in every call.

**The `Length` section shall carry the target and the band and no instruction.** The number arrives by
payload, the rule lives in the agent definition, and neither restates the other. This is a change to
technical §6, which does not yet describe the section at all, and it is recorded there as SI-01.

### 8.2 `assemble(N)` does not describe the section it renders

The pseudocode of technical §6 renders voice, rules, sheets, objective, hook, anchor, digests,
summaries and bridge. It does not render the length instruction, although `page-writer.md` declares
that it receives one and every run to date has supplied one. The value this loop is written around
reaches the writer through a path the technical specification does not describe.

### 8.3 The per-attempt record is a change to the run

SR-01 is the one requirement here that the orchestration must implement rather than the loop. The run
otherwise proceeds exactly as functional §5 describes; what is added is that each validation outcome
is appended as it is decided. No phase, no agent and no gate changes.

---

## 9. Review and change control

### 9.1 Version history

| Version | Date | Changes | Status |
|---|---|---|---|
| 1.0 | 2026-09-18 | Initial version. Scope limited to the target stated in the length instruction. Metric and control signal defined and separated. Learned state introduced as a fourth kind. Epoch, damped and clamped correction, three termination conditions. SR-01 to SR-12, SI-01 to SI-04. | Superseded |
| 2.0 | 2026-09-18 | The calibrated quantity changes from the target to the **wording of rule 2**. The scalar correction of 1.0 §5.2 is withdrawn with `learning.correction_damping` and `learning.bias_tolerance`; the bias becomes a reported diagnostic (2.2). The reviewer that 1.0 §1.3 relied on is replaced by five bounded controls (1.3). Guards added (2.3). Per-attempt record specified, closing the 1.0 blocker (4.2). Loop reports and `paths.loops_dir` added (4.4). Epoch gains `learning.epoch_label` (4.5). Candidate validation C-1 to C-7 (5.4). SR-01 to SR-17. | Draft for review |

### 9.2 Review roles

| Role | Responsibility | Assigned to |
|---|---|---|
| Author | Drafts and maintains this document | [PENDING] |
| Technical reviewer | Verifies the loop is implementable and that its bound is unconditional | [PENDING] |
| Functional reviewer | Verifies that what the loop optimises is what the project wants optimised | [PENDING] |
| Approver | Authorises the move from draft to approved | [PENDING] |

### 9.3 Review checklist

| # | Control point | Result |
|---|---|---|
| SV-01 | Every `learning.*` path referenced here exists in `config.json`, and no `learning` value is unreferenced | |
| SV-02 | No literal value appears in this document where a configuration path belongs | |
| SV-03 | The loop terminates within `learning.max_calibration_runs` observations of one epoch whether or not it converges | |
| SV-04 | No requirement here permits a write outside the current story workspace, except the rendering of 4.4 | |
| SV-05 | No requirement here permits a run to write `config.json`, or the loop to modify any part of an agent definition outside the delimiters | |
| SV-06 | Every requirement of §7 is verifiable from artefacts on disk, without a model call | |
| SV-07 | Nothing here restates a rule that already exists in the other two specifications | |
| SV-08 | The metric of 2.1 is computable from the per-attempt record of 4.2 | |
| SV-09 | The reports of 4.4 are reproducible from the observations alone | |

### 9.4 Change procedure

As functional §11.4. A change here that alters what the loop may touch (5.3), the termination
conditions (5.5) or the metric (2.1) additionally requires review of §8, because those are the three
places where this document depends on the other two.

A change to `learning` in `config.json` requires re-validation of the invariants in §3.

### 9.5 Open issues

| ID | Issue | Impact | Status |
|---|---|---|---|
| SI-01 | The `Length` section of the assembled context restates rule 2 | The loop measures a rewritten rule while an un-rewritten copy arrives in every call. Required by 8.1, and a defect in technical §6 rather than here | **Open — blocking** |
| SI-02 | The criterion was already met at the wording the campaign starts from | Both pilot runs showed a rate of zero, so the loop terminates on entry and learns nothing. `learning.epoch_label` makes a fresh campaign declarable, but whether a rate of zero at a bias away from one should be treated as converged is unresolved, and 2.2 deliberately leaves the bias unable to answer it | Open |
| SI-03 | A run under calibration is not reproducible from `config.json` alone | Two runs at one configuration can be written under different wordings. SR-08 and SR-14 make it visible and recoverable; it remains true | Open |
| SI-04 | Assignment of the roles in 9.2 | Blocks approval of this document | Open |
| SI-05 | The search over wordings has no convergence argument | A scalar correction was contractive; a text is not. The loop is a bounded search with a ratchet on nothing, so a later variant may be worse than an earlier one. The reports of 4.4 make that visible to a person, and `learning.max_calibration_runs` bounds the cost, but the loop cannot itself prefer the best wording it found | **Open — introduced by version 2.0** |
| SI-06 | A wording is judged on one run of `organization.pages_total` pages | At the shipped configuration that is a small sample of a noisy quantity, and one unlucky story can retire a good wording. Raising the sample multiplies the cost of the campaign by whole novels | Open |
