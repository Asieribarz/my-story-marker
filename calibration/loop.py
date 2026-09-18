"""The calibration loop: run, measure, rewrite the instruction, run again.

Self-improvement specification 5. The loop runs *between* runs. Each run writes
what it measured about its own page lengths; when the first-attempt length
failure rate is above `learning.max_first_attempt_length_failure_rate`, the
next run is written under a rewritten length instruction.

What is judgement and what is arithmetic is split the way the rest of the
system splits it (technical 2): proposing a new wording is judgement and is
delegated; deciding whether to keep going, and stopping, is arithmetic and
stays here. A stop is reported, never silent (SR-07).

Two seams, both injected, because neither belongs to this module:

    run_story(story_id, config)  -> {"attempts": [...], "repairs": int}
        one complete run of the flow. This is the orchestrator of technical
        12.3, which does not exist yet; the loop is written against its shape.

    propose(current, evidence, tried) -> str
        one delegation to the length-calibrator agent, which returns a
        candidate instruction and nothing else.

No configuration value is written here (FR-20): every bound arrives from
`config.json` through the caller.
"""

import os

from . import ledger as ledger_module
from . import observation as observation_module
from . import prompt_block
from . import report as report_module


class Stop(object):
    DISABLED = "disabled"
    CONVERGED = "converged"
    CAP_REACHED = "cap_reached"
    NO_VALID_CANDIDATE = "no_valid_candidate"
    TOO_SHORT = "runs_too_short"


def evidence_from(observation):
    """What the calibrator is told about the run it is being asked to improve.
    Numbers only: it is being shown a measurement, not given a target to state."""
    return {
        "rate": observation["rate"],
        "pages": observation["pages"],
        "length_failures": observation["first_attempt_length_failures"],
        "failed_pages": observation["length_failure_pages"],
        "mean_words": observation["mean_words"],
        "bias": observation["bias"],
        "band": observation["band"],
    }


def calibrate(config, derived, agent_path, story_ids, run_story, propose, report=None):
    """Run the flow once per story id, rewriting the instruction between runs.

    Returns the loop report: every run's observation, grouped by the prompt
    variant that produced it, and the condition of 5.3 that stopped it.
    """
    learning = config["learning"]
    say = report or (lambda line: None)

    results, stop = [], None

    if not learning["enabled"]:
        return _report(results, Stop.DISABLED, None)

    stories_root = config["paths"]["stories_root"]
    calibration_path = config["paths"]["calibration"]
    band = derived["word_band"]
    ceiling = learning["max_first_attempt_length_failure_rate"]
    cap = learning["max_calibration_runs"]
    minimum_pages = learning["min_pages_per_observation"]
    max_words = learning["max_length_block_words"]

    tried = _tried_variants(stories_root, calibration_path)

    for index, story_id in enumerate(story_ids[:cap]):
        variant, instruction = prompt_block.read(agent_path)
        epoch = ledger_module.epoch_of(config, variant, prompt_block.digest(instruction))

        say("run %d/%d - story %s under prompt %s" % (index + 1, cap, story_id, variant))
        outcome = run_story(story_id, config)

        observation = observation_module.measure(
            outcome["attempts"], band, epoch, outcome.get("repairs", 0), instruction
        )
        results.append((story_id, observation))

        # SR-02: a run shorter than the floor is reported and contributes nothing.
        if observation["pages"] < minimum_pages:
            say("  %s pages, below the floor of %s: reported, no observation written"
                % (observation["pages"], minimum_pages))
            stop = Stop.TOO_SHORT
            break

        destination = os.path.join(stories_root, story_id, calibration_path)
        observation_module.write(destination, observation)
        tried.setdefault(variant, []).append(observation)
        say("  rate %.3f against a ceiling of %.3f, bias %s"
            % (observation["rate"], ceiling, _round(observation["bias"])))
        render(config, stories_root, ceiling, "running")

        if observation["rate"] <= ceiling:
            stop = Stop.CONVERGED
            say("  at or below the ceiling: the loop is done")
            break

        if index + 1 >= cap:
            stop = Stop.CAP_REACHED
            break

        candidate = _next_instruction(
            propose, instruction, evidence_from(observation), tried, max_words, say
        )
        if candidate is None:
            stop = Stop.NO_VALID_CANDIDATE
            break

        variant = prompt_block.next_variant(variant)
        prompt_block.write(agent_path, candidate, variant)
        say("  instruction rewritten as %s" % variant)

    if stop is None:
        stop = Stop.CAP_REACHED
    render(config, stories_root, ceiling, stop)
    return _report(results, stop, prompt_block.read(agent_path)[0])


def _next_instruction(propose, current, evidence, tried, max_words, say):
    """One delegation, then the mechanical checks. An invalid candidate is not
    written: a prompt that carries a configuration literal breaks FR-20 whether
    a model or a person put it there."""
    candidate = (propose(current, evidence, sorted(tried)) or "").strip()
    problems = prompt_block.validate(candidate, max_words)
    if problems:
        for problem in problems:
            say("  candidate rejected: %s" % problem)
        return None
    if prompt_block.digest(candidate) == prompt_block.digest(current):
        say("  candidate is the instruction already in force")
        return None
    return candidate


def render(config, stories_root, ceiling, stop):
    """Rewrite every Markdown report under `paths.loops_dir` from the
    observations on disk. A rendering, never a source of truth."""
    collected = ledger_module.collect(stories_root, config["paths"]["calibration"])
    instructions = {}
    for _, record in collected:
        variant = (record.get("epoch") or {}).get("prompt_variant")
        if variant and record.get("instruction"):
            instructions[variant] = record["instruction"]
    return report_module.rebuild(
        config["paths"]["loops_dir"], collected, instructions, ceiling, stop
    )


def _tried_variants(stories_root, calibration_path):
    collected = ledger_module.collect(stories_root, calibration_path)
    return {
        variant: [record for _, record in records]
        for variant, records in ledger_module.by_variant(collected).items()
    }


def _round(value):
    return round(value, 3) if isinstance(value, float) else value


def _report(results, stop, variant_in_force):
    by_variant = {}
    for story_id, observation in results:
        variant = observation["epoch"]["prompt_variant"]
        by_variant.setdefault(variant, []).append({
            "story": story_id,
            "rate": observation["rate"],
            "bias": observation["bias"],
            "mean_words": observation["mean_words"],
            "pages": observation["pages"],
            "consistency_rate": observation["consistency_rate"],
            "continuity_repairs": observation["continuity_repairs"],
        })
    return {
        "stop": stop,
        "converged": stop == Stop.CONVERGED,
        "runs": len(results),
        "variant_in_force": variant_in_force,
        "by_variant": by_variant,
    }
