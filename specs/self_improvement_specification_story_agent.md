# Self-improvement specification
## Adventure story generator agent — calibration of the length instruction

| | |
|---|---|
| **Version** | 1.0 |
| **Date** | 18 September 2026 |
| **Governs** | One quantity: the target word count stated in the assembled context of a page call |
| **Depends on** | Functional specification v2.4, technical specification v2.4, `config.json` |
| **Status** | Draft for review |

---

## 1. Scope

This document specifies a loop that runs **between** runs. Each run writes what it measured about its
own page lengths; the next run reads those measurements and states a different target in the context
it assembles. The loop is bounded, it stops on a measured criterion, and it stops unconditionally
after a fixed number of attempts whether or not that criterion is ever met.

It is a third document rather than a section of the other two because it describes a different unit of
work. The functional and technical specifications describe **one run**, from a premise to a manuscript.
Nothing in them crosses a run boundary, and the isolation of a story workspace (FR-42, FR-45) exists
precisely so that nothing does. This loop is the first mechanism that carries anything from one story
to the next, and putting it inside a document whose every requirement is scoped to a single run would
hide the one property most in need of review.

### 1.1 What is calibrated

One thing: **the target stated in the `Length` section of the assembled context**, on the first attempt
at each page. Not the band, not the beat sheet, not an agent definition, not any other parameter.

The choice is not arbitrary. Of every value handed to the writing call, this is the one with measured
evidence against it across three workspaces, the one whose failures all fall in the same direction,
and the one that can be corrected from the system's own output without a human deciding anything.

### 1.2 What this document does not contain

It restates nothing from the other two specifications. Where a rule already exists it is referenced by
its identifier: the length check is FR-10, mechanical validation in code is FR-25, values reaching an
agent by payload is FR-47, no literal outside `config.json` is FR-20, workspace confinement is FR-45,
and the prohibition on an agent writing is FR-49. All of them continue to hold, and this loop is
constrained by every one of them.

### 1.3 The boundary this loop must not cross

Calibration changes a **number in a payload**. It does not change a prompt. The instruction that tells
the writer what to do with that number lives in `page-writer.md`, and that file is where the writing
call's behaviour is defined; a loop able to edit it would be a system rewriting its own instructions
with no reviewer in between. Under FR-47 the number arrives as a value and the agent file carries
none, which is what makes this separation available at all.

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

### 2.2 The control signal

The rate is the **stopping criterion**. It is not what the correction is computed from. The correction
is computed from the **bias**:

```
bias = mean words written over pages that carry a word count
       ----------------------------------------------------
       page.target_words
```

**Why two quantities and not one.** The rate saturates. Once the tolerance band is wide enough to
absorb the overshoot, the rate is zero while the distribution still sits hard against the ceiling, and
a controller reading a saturated signal has nothing to act on. This is not hypothetical: at the
current configuration all three existing workspaces show a first-attempt length rate of zero, with a
bias between 1.03 and 1.09, not one page of ten below target in the most recent run, and one page
landing exactly on the ceiling with no margin. The rate says converged; the distribution says the band
is doing the work the target is supposed to do, and that any future tightening of the tolerance will
bring the retries straight back.

A loop watching only the rate would therefore be correct and useless. A loop watching only the bias
would chase a number nobody is paying for. It needs both, and they do different jobs.

### 2.3 What is deliberately not measured here

Consistency rejections (K1 to K7) and continuity repairs are not part of this metric. They are
judgements about content, they are not caused by the length instruction, and folding them into one
number would produce a controller that moves the word count in response to a character speaking out of
voice.

---

## 3. Configuration

Every value this loop uses is an authoritative input in `config.json`, in a group of its own. This
document names them by path and states no literal (FR-20).

| Path | Governs |
|---|---|
| `learning.enabled` | Whether calibration runs at all |
| `learning.max_first_attempt_length_failure_rate` | The stopping criterion of 2.1 |
| `learning.max_calibration_runs` | The iteration cap, per epoch (4.3) |
| `learning.min_pages_per_observation` | The shortest run that may contribute an observation |
| `learning.correction_damping` | How much of the measured bias one iteration corrects (5.2) |
| `learning.bias_tolerance` | How close to 1 the bias must be for the loop to consider itself done |

**Invariants.** The configuration is invalid, and the run does not start, unless
`learning.max_first_attempt_length_failure_rate` and `learning.bias_tolerance` lie in `(0, 1)`,
`learning.correction_damping` lies in `(0, 1]`, and `learning.max_calibration_runs` and
`learning.min_pages_per_observation` are each at least 1. These extend the list in functional
specification §2.3 and are checked on the same path, before the first model call (FR-21).

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
| `epoch` | `page.target_words` and `page.length_tolerance` as this run read them |
| `asked` | the target the `Length` section actually carried, which is the calibrated value and not necessarily the configured one |
| `band` | the accepted band the FR-10 check used |
| `pages` | pages written, each counted once |
| `first_attempt_length_failures` | the numerator of 2.1 |
| `mean_words` | the mean over pages that carry a word count |
| `bias` | as defined in 2.2 |

A state record with no word count is not a page of zero words: it is a page whose length was never
logged. It is excluded from `mean_words` and named in the observation, never averaged in.

### 4.2 The ledger is a projection, not a file

The **calibration ledger** is obtained by reading the observation of every workspace under
`paths.stories_root` and keeping those whose `epoch` matches the current configuration. Nothing writes
it.

This mirrors the thread register of functional §4.2, which is likewise a replay projection rather than
a stored file, and for the same reason: a ledger held as a shared file would be a value two runs could
disagree about, and it would be the first thing in this design to live outside a story workspace. A
run writes one observation, inside its own workspace, and touches no other (FR-45). Reading across
workspaces is permitted; writing across them is not, and that asymmetry is the whole of what keeps
this loop compatible with story isolation.

### 4.3 The epoch, and why the cap needs one

The iteration cap counts observations **in the current epoch only**. When an operator edits
`page.target_words` or `page.length_tolerance`, every earlier observation describes a system that no
longer exists: the ledger for the new epoch is empty and the cap is full again.

Without an epoch the cap would be spent once and for all, and the loop could never be re-armed by the
very change that most needs measuring — which, per 2.2, is a tightening of the tolerance.

---

## 5. The loop

### 5.1 Where it touches the run

Two steps, both in code, both additions to the flow of functional §5. Neither is a delegation and
neither has an agent: reading a ledger, taking a ratio and clamping it are arithmetic, and a
correction produced by a model judgement could not be replayed — while its output goes into every page
call of the run that follows.

| Step | Phase | Action |
|---|---|---|
| **A0b** | after A0 | Read the calibration ledger, compute the asked target, report it (5.4) |
| **C6** | after C5 | Write this run's calibration observation |

C6 sits after the closing report so that the report describes the run, not the loop.

### 5.2 The correction

```
if the loop is stopped (5.3):
    asked = page.target_words
else:
    bias  = mean of the bias over the observations in the current epoch
    asked = page.target_words / bias ** learning.correction_damping
    asked = clamp(asked, into the band derived from page.target_words
                         and page.length_tolerance)
```

Three properties are required, and each removes a failure this arithmetic would otherwise have:

- **Damped.** A full correction on a sample of one run overshoots, and the next run corrects back the
  other way. `learning.correction_damping` is what makes the sequence converge rather than oscillate.
- **Clamped.** The asked target never leaves the accepted band. An unclamped correction can formally
  ask for a page that the FR-10 check would reject on arrival, which is a controller asking for a
  failure.
- **Averaged over the epoch, not over the last run.** One run is one sample of a noisy quantity.

**The band never moves.** It is derived from the operator's configuration and it is the requirement;
only the number the writer is asked to aim at changes. Moving both would lower the bar and measure
nothing.

### 5.3 Termination

The loop is stopped, and the asked target equals `page.target_words` from then on, when any of these
holds:

1. `learning.enabled` is false;
2. the ledger for the current epoch holds `learning.max_calibration_runs` observations;
3. the most recent observation shows a rate at or below
   `learning.max_first_attempt_length_failure_rate` **and** a bias within `learning.bias_tolerance`
   of 1.

Condition 2 is the fixed bound. It is checked before condition 3, it does not depend on the
measurement converging, and it is the reason this loop cannot run forever. Reaching it without
satisfying condition 3 is a legitimate outcome, not an error — and it must be **reported**, never
silent, in the manner of a superseded configuration value (FR-37). A loop that quietly gave up would
leave the operator believing a calibration was still in progress.

### 5.4 What is reported

Where the asked target differs from `page.target_words`, the difference, the bias it came from and the
position of the run in the calibration sequence are reported at start-up and in the closing report.

This is not decoration. A run under calibration is **not reproducible from `config.json` alone**: two
runs at one configuration can be asked for different targets, because the second read the first's
observation. That is an acceptable cost of a loop that learns, but only if every run says what it was
asked for. `learning.enabled` set to false is what makes a clean measurement run possible, and the
existing workspaces must be understood as uncalibrated by construction rather than by declaration.

### 5.5 What the loop may never change

The asked target, and nothing else. Not the band, not `config.json`, not the beat sheet, not a
character sheet, not an agent definition, and not the wording of any instruction. A change to the set
of things this loop may touch is a change to this document, reviewed under §9.

---

## 6. The metric command

A command that answers, from the artefacts on disk and with no model call: **what is the rate, and
where is it going.**

```
story-metric length [--story <id>] [--json]
```

| Output | Source |
|---|---|
| Per workspace: pages, first-attempt length failures, rate, asked, mean words, bias | that workspace's calibration observation (4.1) |
| Across the current epoch: the rate and bias of each observation in order, and the mean bias | the ledger projection (4.2) |
| The loop's position: observations made, the cap, and which condition of 5.3 currently holds | the ledger and `config.json` |
| Any workspace excluded from the ledger, named, with the reason | comparison of `epoch` against `config.json` |

`--json` emits the same content as data, so the metric can be tracked over time by something other
than a reader.

The command recomputes nothing the run already measured; it reads observations and reports them. Where
a workspace predates this specification and has no observation, the command reports what that
workspace **can** still support — pages, mean words and bias, all recoverable from the state log — and
states that the rate is unavailable for it. That degraded mode is required rather than optional: at
the time of writing it is the only mode any existing workspace can satisfy, for the reason in §8.

---

## 7. Requirements

| ID | Requirement |
|---|---|
| SR-01 | The system shall record, per page attempt, whether that attempt was rejected and by which check, so that the metric of 2.1 is computable from the state log. |
| SR-02 | On closing a run that wrote at least `learning.min_pages_per_observation` pages, the system shall write the calibration observation of 4.1 to `paths.calibration`. A shorter run shall be reported but shall contribute no observation. |
| SR-03 | The calibration ledger shall be obtained by reading the observation of each workspace under `paths.stories_root` and retaining those whose epoch matches the current configuration. It shall not be stored. |
| SR-04 | The target stated in the `Length` section of the assembled context shall be the value computed in 5.2, and shall lie inside the band derived from `page.target_words` and `page.length_tolerance`. |
| SR-05 | No run shall write `config.json`, and no learned value shall be stored in it. |
| SR-06 | Calibration shall stop under any condition of 5.3, and condition 2 shall be evaluated before condition 3. |
| SR-07 | Reaching `learning.max_calibration_runs` without satisfying the measured criterion shall be reported as an unconverged termination, with the observations made, and the system shall continue to write stories at `page.target_words`. |
| SR-08 | Where the asked target differs from `page.target_words`, the difference, the bias and the position in the calibration sequence shall be reported at start-up and in the closing report. |
| SR-09 | Calibration shall change no value other than the asked target, and shall not modify any agent definition. |
| SR-10 | The command of §6 shall report the metric without invoking a model, and shall name any workspace it excluded from the ledger and why. |
| SR-11 | A page whose state record carries no word count shall be excluded from `mean_words` and named, and shall never be averaged in as a page of zero words. |
| SR-12 | Calibration steps A0b and C6 shall be executed in code by the orchestrator, with no delegation. |

---

## 8. Dependency: the metric is not recordable today

**SR-01 is a prerequisite, not a refinement, and it is the one thing that blocks building the rest.**

The state record defined in functional §4.2 carries a `retries` count. It does not carry what each
attempt was rejected *for*. From `retries: 2` it is impossible to tell whether the first attempt was
too long, contradicted a world rule, or gave a character the wrong arithmetic — and the metric of 2.1
needs exactly that distinction.

This is not a theoretical gap. In the most recent run both of one page's retries were consistency
failures, K4 and K3, and none was a length failure; that fact survives only because a human wrote it
into the closing report in prose. Replayed from the state log alone, that page is indistinguishable
from a page that overran the band twice.

Two consequences follow, and both are deliberate:

- the loop cannot be built before the state record carries per-attempt rejection reasons, which is a
  change to functional §4.2 and to FR-15, made under the procedure of functional §11.4 and not here;
- the command of §6 must therefore ship with its degraded mode, because until that change lands there
  is no workspace whose rate it can compute.

**A second, smaller gap.** The `assemble(N)` pseudocode of technical §6 renders voice, rules, sheets,
objective, hook, anchor, digests, summaries and bridge. It does not render the length instruction —
although `page-writer.md` declares that it receives one, and every run to date has supplied one. The
value this document calibrates therefore reaches the writer through a path the technical specification
does not describe. That is a defect in technical §6 and is recorded as SI-01.

---

## 9. Review and change control

### 9.1 Version history

| Version | Date | Changes | Status |
|---|---|---|---|
| 1.0 | 2026-09-18 | Initial version. Scope limited to the target stated in the length instruction. Metric and control signal defined, and separated. Learned state introduced as a fourth kind, held per workspace and projected into a ledger. Epoch, damped and clamped correction, and three termination conditions with a fixed cap. Metric command specified, with a degraded mode. SR-01 to SR-12, SI-01 to SI-04. | Draft for review |

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
| SV-04 | No requirement here permits a write outside the current story workspace | |
| SV-05 | No requirement here permits a run to write `config.json` or to modify an agent definition | |
| SV-06 | Every requirement of §7 is verifiable from artefacts on disk, without a model call | |
| SV-07 | Nothing here restates a rule that already exists in the other two specifications | |
| SV-08 | The metric of 2.1 is computable from the state record as functional §4.2 defines it | |

### 9.4 Change procedure

As functional §11.4. A change here that alters what the loop may touch (5.5), the termination
conditions (5.3) or the metric (2.1) additionally requires review of §8, because those are the three
places where this document depends on the other two.

A change to `learning` in `config.json` requires re-validation of the invariants in §3.

### 9.5 Open issues

| ID | Issue | Impact | Status |
|---|---|---|---|
| SI-01 | `assemble(N)` in technical §6 does not render the length instruction, although the writing agent declares it receives one | The value this document calibrates reaches the writer by a path the technical specification does not describe, so the loop's output has no specified destination | **Open — blocking**, and it is a defect in technical §6 rather than here |
| SI-02 | The stopping criterion is already satisfied at the current configuration | All three existing workspaces show a first-attempt length rate of zero, so the loop terminates on entry and learns nothing, while the bias sits between 1.03 and 1.09. As specified, this is a guard that re-arms when the target or the tolerance changes rather than a mechanism that improves the present configuration. Whether the bias condition alone should be able to start it is unresolved | Open |
| SI-03 | A run under calibration is not reproducible from `config.json` alone | Two runs at one configuration can be asked for different targets. SR-08 makes it visible and `learning.enabled` makes it defeasible, but the measurement runs that are this project's only evidence must now be declared uncalibrated rather than being so by construction | Open |
| SI-04 | Assignment of the roles in 9.2 | Blocks approval of this document | Open |
