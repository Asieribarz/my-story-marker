"""Driving the calibration loop when the orchestrator is a session, not a script.

The runs of this project are orchestrated by an agent session rather than by
`run.py`, which does not exist (technical 12.3). That does not change the
division this system is built on: what is arithmetic is executed, what is
judgement is delegated (technical 2). Here the session performs the two steps
that are judgement - writing the story, and rewriting the instruction - and
every number is computed by this module, from artefacts on disk, with no model
call (SR-10).

One iteration of the loop:

    python -m calibration.cli status
        the ledger by prompt variant, and which condition of 5.3 holds now.

    python -m calibration.cli measure <story-id> --attempts <file.jsonl>
        after a run: write the observation of that run, print the rate against
        the ceiling, and say whether the loop continues. When it does, print
        the evidence to hand to the length-calibrator.

    python -m calibration.cli apply --instruction <file>
        validate a candidate instruction and replace the delimited block,
        bumping the variant. Refuses a candidate that carries a configuration
        literal, drops the subject, or exceeds its ceiling.

The attempts file is JSON Lines, one record per page attempt, written while
the run is orchestrated:

    {"page": 7, "attempt": 1, "words": 412, "rejected_by": ["length"]}
"""

import argparse
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from calibration import ledger as ledger_module
from calibration import loop as loop_module
from calibration import observation as observation_module
from calibration import prompt_block
from calibration import report as report_module
from ui import derive as derivation

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(ROOT, "config.json")
AGENT_PATH = os.path.join(ROOT, ".claude", "agents", "page-writer.md")


def _setup():
    config = derivation.load(CONFIG_PATH)
    derived = derivation.derive(config)
    problems = derivation.validate(config, derived)
    if problems and config["control"]["abort_on_invalid_config"]:
        for problem in problems:
            print("config: %s" % problem)
        raise SystemExit(1)
    variant, instruction = prompt_block.read(AGENT_PATH)
    epoch = ledger_module.epoch_of(config, variant, prompt_block.digest(instruction))
    return config, derived, variant, instruction, epoch


def _observation_path(config, story_id):
    return os.path.join(
        ROOT, config["paths"]["stories_root"], story_id, config["paths"]["calibration"]
    )


def _read_attempts(path):
    records = []
    with io.open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def status(args):
    config, derived, variant, instruction, epoch = _setup()
    stories_root = os.path.join(ROOT, config["paths"]["stories_root"])
    collected = ledger_module.collect(stories_root, config["paths"]["calibration"])
    kept, excluded = ledger_module.for_epoch(collected, epoch)
    learning = config["learning"]
    band = derived["word_band"]

    print("instruction in force: %s  (%s)" % (variant, prompt_block.digest(instruction)))
    print("  %s" % instruction.replace("\n", "\n  "))
    print("band: %s to %s words, target %s" % (band["min"], band["max"], band["target"]))
    print("")

    grouped = ledger_module.by_variant(collected)
    if not grouped:
        print("no observations on disk yet.")
    for name in sorted(grouped):
        records = [record for _, record in grouped[name]]
        print("prompt %s - %s observation(s)" % (name, len(records)))
        for story_id, record in grouped[name]:
            print("  %-24s rate %s  bias %s  mean %s over %s pages"
                  % (story_id, _fmt(record["rate"]), _fmt(record["bias"]),
                     _fmt(record["mean_words"]), record["pages"]))
        print("  mean rate %s, mean bias %s"
              % (_fmt(ledger_module.mean([r["rate"] for r in records])),
                 _fmt(ledger_module.mean([r["bias"] for r in records]))))

    if excluded:
        print("")
        for story_id, reason in excluded:
            print("excluded from the current epoch: %s (%s)" % (story_id, reason))

    print("")
    print("observations in this epoch: %s of %s" % (len(kept), learning["max_calibration_runs"]))
    print("stop condition now: %s" % _stop_now(kept, learning))


def _stop_now(kept, learning):
    if not learning["enabled"]:
        return "%s - learning.enabled is false" % loop_module.Stop.DISABLED
    if len(kept) >= learning["max_calibration_runs"]:
        return ("%s - the cap is spent; report the loop as unconverged unless the last "
                "observation met the ceiling (SR-07)" % loop_module.Stop.CAP_REACHED)
    if kept:
        last = kept[-1][1]
        ceiling = learning["max_first_attempt_length_failure_rate"]
        if last["rate"] is not None and last["rate"] <= ceiling:
            return "%s - the last rate is at or below the ceiling" % loop_module.Stop.CONVERGED
    return "running - the loop continues"


def measure(args):
    config, derived, variant, instruction, epoch = _setup()
    learning = config["learning"]
    attempts = _read_attempts(args.attempts)
    record = observation_module.measure(
        attempts, derived["word_band"], epoch, args.repairs, instruction
    )

    print("story %s under prompt %s" % (args.story, variant))
    print("  pages                      %s" % record["pages"])
    print("  first-attempt length fails %s  %s"
          % (record["first_attempt_length_failures"], record["length_failure_pages"] or ""))
    print("  rate                       %s  (ceiling %s)"
          % (_fmt(record["rate"]), learning["max_first_attempt_length_failure_rate"]))
    print("  mean words / bias          %s / %s"
          % (_fmt(record["mean_words"]), _fmt(record["bias"])))
    print("  guards: consistency %s, continuity repairs %s"
          % (_fmt(record["consistency_rate"]), record["continuity_repairs"]))
    if record["pages_without_word_count"]:
        print("  pages with no word count   %s (excluded from the mean, SR-11)"
              % record["pages_without_word_count"])

    if record["pages"] < learning["min_pages_per_observation"]:
        print("")
        print("reported but not written: %s pages is below the floor of %s (SR-02)."
              % (record["pages"], learning["min_pages_per_observation"]))
        return

    destination = _observation_path(config, args.story)
    observation_module.write(destination, record)
    print("")
    print("observation written to %s" % os.path.relpath(destination, ROOT))
    for path in _render(config, learning, "running"):
        print("report %s" % os.path.relpath(path, ROOT))

    if record["rate"] <= learning["max_first_attempt_length_failure_rate"]:
        print("")
        print("STOP - converged. The rate is at or below the ceiling; leave the instruction "
              "as it is.")
        return

    stories_root = os.path.join(ROOT, config["paths"]["stories_root"])
    collected = ledger_module.collect(stories_root, config["paths"]["calibration"])
    grouped = ledger_module.by_variant(collected)
    total = sum(len(records) for records in grouped.values())
    if total >= learning["max_calibration_runs"]:
        print("")
        print("STOP - the cap of %s observations is spent and the rate never reached the "
              "ceiling. Report this as an unconverged termination (SR-07) and keep writing "
              "at the instruction in force." % learning["max_calibration_runs"])
        return

    print("")
    print("CONTINUE - rewrite the length instruction. Hand the length-calibrator:")
    print(json.dumps({
        "current_instruction": instruction,
        "evidence": loop_module.evidence_from(record),
        "variants_already_tried": sorted(grouped),
        "ceiling_words": learning["max_length_block_words"],
    }, indent=2, ensure_ascii=False))
    print("")
    print("then: python -m calibration.cli apply --instruction <file>")


def _render(config, learning, stop):
    stories_root = os.path.join(ROOT, config["paths"]["stories_root"])
    return loop_module.render(
        config, stories_root, learning["max_first_attempt_length_failure_rate"], stop
    )


def record(args):
    """Append one page attempt while the flow is being orchestrated.

    This is the per-attempt rejection reason the state record of functional 4.2
    does not carry, and without which the metric of 2.1 is not computable from
    disk (SR-01). It is appended by code rather than typed, so that what the
    loop measures is what the validation decided.
    """
    config, _, _, _, _ = _setup()
    path = os.path.join(
        ROOT, config["paths"]["stories_root"], args.story,
        config["paths"]["runs_dir"], args.run, "attempts.jsonl"
    )
    directory = os.path.dirname(path)
    if not os.path.isdir(directory):
        os.makedirs(directory)
    row = {
        "page": args.page,
        "attempt": args.attempt,
        "words": args.words,
        "rejected_by": args.rejected or [],
    }
    with io.open(path, "a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    print("%s  page %s attempt %s: %s words, %s"
          % (os.path.relpath(path, ROOT), args.page, args.attempt, args.words,
             ", ".join(row["rejected_by"]) or "accepted"))


def rebuild_reports(args):
    config, _, _, _, _ = _setup()
    for path in _render(config, config["learning"], args.stop):
        print(os.path.relpath(path, ROOT))


def apply_candidate(args):
    config, _, variant, instruction, _ = _setup()
    candidate = io.open(args.instruction, encoding="utf-8").read().strip()
    problems = prompt_block.validate(candidate, config["learning"]["max_length_block_words"])
    if prompt_block.digest(candidate) == prompt_block.digest(instruction):
        problems.append("the candidate is the instruction already in force.")
    if problems:
        for problem in problems:
            print("rejected: %s" % problem)
        raise SystemExit(1)

    new_variant = prompt_block.next_variant(variant)
    prompt_block.write(AGENT_PATH, candidate, new_variant)
    print("%s -> %s" % (variant, new_variant))
    print(candidate)
    print("")
    print("the epoch has changed: the ledger for %s is empty and the cap is full again (4.3)."
          % new_variant)
    print("commit the file - a run is not reproducible from a prompt that lives only on disk.")


def _fmt(value):
    if value is None:
        return "-"
    if isinstance(value, float):
        return "%.3f" % value
    return str(value)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="calibration")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("status").set_defaults(function=status)

    measured = subparsers.add_parser("measure")
    measured.add_argument("story")
    measured.add_argument("--attempts", required=True)
    measured.add_argument("--repairs", type=int, default=0)
    measured.set_defaults(function=measure)

    recorded = subparsers.add_parser("record")
    recorded.add_argument("story")
    recorded.add_argument("--run", required=True, help="the run directory, e.g. 2026-09-18T12-00")
    recorded.add_argument("--page", type=int, required=True)
    recorded.add_argument("--attempt", type=int, required=True)
    recorded.add_argument("--words", type=int)
    recorded.add_argument("--rejected", nargs="*", default=[],
                          help='"length", "roster", "structure", or K1 ... K7')
    recorded.set_defaults(function=record)

    rebuilt = subparsers.add_parser("report")
    rebuilt.add_argument("--stop", default="running")
    rebuilt.set_defaults(function=rebuild_reports)

    applied = subparsers.add_parser("apply")
    applied.add_argument("--instruction", required=True)
    applied.set_defaults(function=apply_candidate)

    args = parser.parse_args(argv)
    if not getattr(args, "function", None):
        parser.print_help()
        return 0
    return args.function(args) or 0


if __name__ == "__main__":
    raise SystemExit(main())
