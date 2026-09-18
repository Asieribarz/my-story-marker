# Running a calibration campaign

How to run the loop of `specs/self_improvement_specification_story_agent.md` v2.0 from a fresh
session. The orchestrator is the session; every number in it is computed by
`python -m calibration.cli`, never asserted.

One iteration is **one complete story**, written exactly as functional §5 describes. The orchestration
does not change. What is added is one command per page attempt, and three commands around each story.

---

## Before the first iteration

1. **Name the campaign.** Set `learning.epoch_label` in `config.json` to something that has not been
   used. Observations of earlier campaigns stay on disk and fall out of the ledger by name (4.5); they
   are never deleted.
2. **Check the starting point.** `python -m calibration.cli status` must print `0 of N` observations
   and `running`. If it prints observations you did not write in this campaign, the label is not fresh.
3. **Commit the wording in force** before writing anything under it (SR-14).

## Per iteration

```
# 1. Confirm which wording is in force and that the loop is still running.
python -m calibration.cli status

# 2. Write one complete story into its own workspace, from the next premise,
#    under that wording. Phases A, B and C exactly as functional section 5.
#    While doing it, after each page attempt is validated:
python -m calibration.cli record <story-id> --run <run-dir> \
    --page N --attempt N --words N --rejected length

#    --rejected takes the checks that rejected the attempt: length, roster,
#    structure, or K1 ... K7. Omit it when the attempt was accepted.

# 3. Measure the finished flow.
python -m calibration.cli measure <story-id> \
    --attempts stories/<story-id>/runs/<run-dir>/attempts.jsonl --repairs N

#    It prints the rate against the ceiling and then either
#      STOP     - the criterion is met, the campaign is over; or
#      STOP     - the cap is spent, report it as unconverged (SR-07); or
#      CONTINUE - with the payload to hand to length-calibrator.

# 4. Only on CONTINUE: delegate to length-calibrator with that payload,
#    write what it returns to a file, and apply it.
python -m calibration.cli apply --instruction <file>

# 5. Commit the rewritten page-writer.md before the next iteration (SR-14).
```

`measure` re-renders `loops/` on every call, so the campaign is readable at any point from
`loops/summary.md`.

---

## The three things that are easy to get wrong

**One story per iteration, one workspace per story, one premise per story** (SR-17). Re-using a story
id makes resume find no missing page and write nothing (TR-17), and re-using a workspace under a
different premise stops the run outright (TR-19-0). Six iterations need six ids and six premises.

**Record the attempt, not the outcome.** `record` is called once per *attempt*, including the ones
that were rejected — the metric of 2.1 counts first attempts, so a run that only logs the accepted
page measures nothing (SR-01).

**The `Length` section of the assembled context carries the target and the band and no instruction**
(8.1). The rule lives in `page-writer.md` and the payload must not restate it; while it does, the loop
is measuring a rewritten rule with an un-rewritten copy arriving in every call. This is SI-01 and it is
blocking.

---

## Launching it in one shot

Paste this into a fresh session. The premises are the six of campaign-01; replace them for a later
campaign, and change `learning.epoch_label` to match.

```
You are the orchestrator of a calibration campaign. Read, in this order:
CLAUDE.md, specs/self_improvement_specification_story_agent.md (v2.0), loops/RUNBOOK.md,
and specs/functional_specification_story_agent.md section 5.

The campaign runs one complete story per iteration. The orchestration of each story is
exactly the one in functional section 5 and does not change: you delegate to bible-builder,
page-writer, consistency-checker, continuity-auditor and closing-auditor. You never write
prose yourself, you never merge two call types into one invocation (page and consistency
above all), and you label every delegation with its call type, its page and, on a retry,
its attempt number.

Read every bound from config.json. Do not write config.json. Do not edit any agent
definition by hand - the only permitted change is rule 2 of page-writer.md, through
`python -m calibration.cli apply`.

The Length section of the context you assemble for each page carries the target and the
band and NO instruction. What the writer does with those numbers is rule 2 of
page-writer.md and is written there only.

BEFORE STARTING
  Confirm `python -m calibration.cli status` reports zero observations in this epoch and
  that the loop is running. Confirm page-writer.md is committed. If either is not true,
  stop and say so.

PER ITERATION
  1. `python -m calibration.cli status` - note the wording in force.
  2. Write the whole story into its own workspace from the next premise below.
     After each page attempt is validated, immediately:
       python -m calibration.cli record <story-id> --run <run-dir>
           --page N --attempt N --words N --rejected <checks>
     Record EVERY attempt, including rejected ones. Omit --rejected when accepted.
  3. `python -m calibration.cli measure <story-id> --attempts <path> --repairs N`
  4. On CONTINUE: delegate to length-calibrator with the payload it printed, write the
     returned wording to a file, `python -m calibration.cli apply --instruction <file>`,
     commit page-writer.md, and go to the next premise.
     On STOP: stop the campaign.

PREMISES, one per iteration, in order:
  1. the-glass-ferry    - A ferryman who has worked one strait for thirty years is paid to
                          carry a passenger who must not be allowed to reach the far shore.
  2. the-ninth-lantern  - On an island whose lanterns are lit nightly to keep something
                          offshore, the keeper's daughter finds that one of them has been
                          dark for years and nobody will say which.
  3. the-paper-mountain - A cartographer is sent to survey a mountain that appears on every
                          old map of the province and on none of the new ones.
  4. the-quiet-flood    - Two rivals descend into a valley being deliberately drowned, to
                          recover something from a town with one day left above the water.
  5. the-last-caravan   - The final caravan of the season must cross a desert whose only
                          well is held by someone who knew the guide before.
  6. the-iron-orchard   - A botanist returns to the family orchard to find the trees
                          replaced by machines, and must decide what is worth harvesting.

AT THE END
  Report from loops/summary.md: every wording tried with its rate, whether the campaign
  converged, which condition of 5.5 stopped it, and whether any guard of 2.3 worsened
  against the first iteration. Do not recompute any number - read them.
```

## What stops the campaign

| Condition | What it means |
|---|---|
| Rate at or below the ceiling | Converged. The wording in force is the answer |
| `learning.max_calibration_runs` observations spent | Unconverged. Report it, with every wording tried and its rate (SR-07). The system keeps writing under the wording in force |
| A candidate fails a check of 5.4 | The loop stops rather than write an invalid instruction. Report which check |
| A guard worsened while the rate converged | Qualified convergence (5.5). The loop stops, but the outcome is not a clean success |
