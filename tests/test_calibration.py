"""Tests for the calibration loop.

Every requirement of the self-improvement specification that is meaningful only
as an executed check: the metric of 2.1, the epoch of 4.3, the mechanical
validation of a candidate instruction, and the termination of 5.3.

    python -m unittest discover tests
"""

import io
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from calibration import ledger, loop, observation, prompt_block
from ui import derive

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BAND = {"target": 380, "min": 304, "max": 456}
EPOCH = {"epoch_label": "campaign-01", "target_words": 380, "length_tolerance": 0.2,
         "prompt_variant": "v1", "prompt_digest": "abc123"}

AGENT = """---
name: page-writer
---

## Rules

1. **Accomplish the objective.**
2. <!-- calibrated:length v1 -->
   **Write to the target length, not past it.** Aim at the target and stop.
   <!-- /calibrated -->
3. **An anchor page turns the story.**
"""


def attempt(page, number, words, rejected=None):
    return {"page": page, "attempt": number, "words": words, "rejected_by": rejected or []}


class TestMetric(unittest.TestCase):
    """2.1: the rate counts each page once, at its first attempt."""

    def test_rate_counts_first_attempts_only(self):
        attempts = [
            attempt(1, 1, 470, ["length"]),
            attempt(1, 2, 390),          # the retry must not count
            attempt(2, 1, 380),
            attempt(3, 1, 300, ["length"]),
            attempt(4, 1, 380),
        ]
        record = observation.measure(attempts, BAND, EPOCH)
        self.assertEqual(record["pages"], 4)
        self.assertEqual(record["first_attempt_length_failures"], 2)
        self.assertEqual(record["length_failure_pages"], [1, 3])
        self.assertAlmostEqual(record["rate"], 0.5)

    def test_consistency_rejections_are_a_guard_not_the_metric(self):
        """2.3: a K-check rejection must never move the length metric."""
        attempts = [attempt(1, 1, 380, ["K4", "K3"]), attempt(2, 1, 380)]
        record = observation.measure(attempts, BAND, EPOCH)
        self.assertEqual(record["first_attempt_length_failures"], 0)
        self.assertEqual(record["rate"], 0)
        self.assertEqual(record["first_attempt_consistency_rejections"], 1)
        self.assertAlmostEqual(record["consistency_rate"], 0.5)

    def test_page_without_word_count_is_named_not_averaged(self):
        """SR-11: it is not a page of zero words."""
        attempts = [attempt(1, 1, 400), attempt(2, 1, None)]
        record = observation.measure(attempts, BAND, EPOCH)
        self.assertEqual(record["mean_words"], 400)
        self.assertEqual(record["pages_without_word_count"], [2])
        self.assertAlmostEqual(record["bias"], 400 / 380)


class TestBlock(unittest.TestCase):
    """The delimited block: read, validate, replace, and nothing else moves."""

    def setUp(self):
        self.directory = tempfile.mkdtemp()
        self.path = os.path.join(self.directory, "page-writer.md")
        io.open(self.path, "w", encoding="utf-8", newline="\n").write(AGENT)

    def tearDown(self):
        shutil.rmtree(self.directory)

    def test_read(self):
        variant, text = prompt_block.read(self.path)
        self.assertEqual(variant, "v1")
        self.assertTrue(text.startswith("**Write to the target length"))

    def test_write_touches_only_the_block(self):
        prompt_block.write(self.path, "**Stop at the target.** Do not exceed it.", "v2")
        updated = io.open(self.path, encoding="utf-8").read()
        self.assertIn("1. **Accomplish the objective.**", updated)
        self.assertIn("3. **An anchor page turns the story.**", updated)
        self.assertNotIn("not past it", updated)
        variant, text = prompt_block.read(self.path)
        self.assertEqual(variant, "v2")
        self.assertEqual(text, "**Stop at the target.** Do not exceed it.")

    def test_a_digit_is_refused(self):
        """FR-20 / V-13: the number arrives by payload, never in the prompt."""
        problems = prompt_block.validate("**Write 380 words.**", 40)
        self.assertTrue(any("digit" in problem for problem in problems))

    def test_dropping_the_subject_is_refused(self):
        problems = prompt_block.validate("**Write well and stop when you are done.**", 40)
        self.assertTrue(any("no longer mentions length" in problem for problem in problems))

    def test_an_empty_block_is_refused(self):
        self.assertTrue(prompt_block.validate("   ", 40))

    def test_the_ceiling_is_enforced(self):
        long_candidate = "target " * 60
        problems = prompt_block.validate(long_candidate, 40)
        self.assertTrue(any("ceiling" in problem for problem in problems))

    def test_variant_is_bumped(self):
        self.assertEqual(prompt_block.next_variant("v1"), "v2")
        self.assertEqual(prompt_block.next_variant("v9"), "v10")


class TestEpoch(unittest.TestCase):
    """4.3: a run written under a different prompt is a different system."""

    def test_a_new_campaign_excludes_earlier_observations(self):
        """4.5: the label is how an operator re-arms the loop without deleting evidence."""
        collected = [("a", {"epoch": dict(EPOCH, epoch_label="pilot")})]
        kept, excluded = ledger.for_epoch(collected, EPOCH)
        self.assertEqual(kept, [])
        self.assertIn("epoch_label", excluded[0][1])

    def test_a_changed_prompt_excludes_the_observation(self):
        collected = [
            ("a", {"epoch": dict(EPOCH), "rate": 0.1}),
            ("b", {"epoch": dict(EPOCH, prompt_variant="v2"), "rate": 0.4}),
        ]
        kept, excluded = ledger.for_epoch(collected, EPOCH)
        self.assertEqual([story for story, _ in kept], ["a"])
        self.assertEqual(excluded[0][0], "b")
        self.assertIn("prompt_variant", excluded[0][1])

    def test_an_edited_prompt_that_kept_its_name_is_caught(self):
        """The digest is what stops two different texts looking like one variant."""
        collected = [("a", {"epoch": dict(EPOCH, prompt_digest="different")})]
        kept, excluded = ledger.for_epoch(collected, EPOCH)
        self.assertEqual(kept, [])
        self.assertIn("prompt_digest", excluded[0][1])

    def test_results_are_grouped_by_prompt(self):
        collected = [
            ("a", {"epoch": dict(EPOCH)}),
            ("b", {"epoch": dict(EPOCH)}),
            ("c", {"epoch": dict(EPOCH, prompt_variant="v2")}),
        ]
        grouped = ledger.by_variant(collected)
        self.assertEqual(sorted(grouped), ["v1", "v2"])
        self.assertEqual(len(grouped["v1"]), 2)


class TestLoop(unittest.TestCase):
    """5.3: the loop stops on the criterion, and unconditionally on the cap."""

    def setUp(self):
        self.directory = tempfile.mkdtemp()
        self.agent = os.path.join(self.directory, "page-writer.md")
        io.open(self.agent, "w", encoding="utf-8", newline="\n").write(AGENT)
        self.config = {
            "page": {"target_words": 380, "length_tolerance": 0.2},
            "paths": {"stories_root": os.path.join(self.directory, "stories"),
                      "loops_dir": os.path.join(self.directory, "loops"),
                      "calibration": os.path.join("state", "calibration.json")},
            "learning": {"enabled": True, "max_first_attempt_length_failure_rate": 0.2,
                         "max_calibration_runs": 3, "min_pages_per_observation": 2,
                         "max_length_block_words": 40, "epoch_label": "test"},
        }
        self.derived = {"word_band": BAND}

    def tearDown(self):
        shutil.rmtree(self.directory)

    def _run(self, rates):
        """A run whose first-attempt length failure rate is dictated by `rates`."""
        self.calls = []

        def run_story(story_id, config):
            rate = rates[len(self.calls)]
            self.calls.append(story_id)
            pages = 10
            failures = int(round(rate * pages))
            attempts = [attempt(n, 1, 400, ["length"]) for n in range(1, failures + 1)]
            attempts += [attempt(n, 1, 380) for n in range(failures + 1, pages + 1)]
            return {"attempts": attempts, "repairs": 0}

        def propose(current, evidence, tried):
            # No digit: a candidate that carries one is refused, and rightly.
            wording = ("once", "twice", "again", "yet again")[len(self.calls) - 1]
            return "**Stop at the target length, %s told.** Do not write past it." % wording

        return run_story, propose

    def test_stops_when_the_rate_meets_the_ceiling(self):
        run_story, propose = self._run([0.5, 0.1])
        report = loop.calibrate(self.config, self.derived, self.agent,
                                ["one", "two", "three"], run_story, propose)
        self.assertEqual(report["stop"], loop.Stop.CONVERGED)
        self.assertTrue(report["converged"])
        self.assertEqual(report["runs"], 2)
        # The instruction was rewritten once, between the two runs.
        self.assertEqual(report["variant_in_force"], "v2")
        self.assertEqual(sorted(report["by_variant"]), ["v1", "v2"])

    def test_stops_on_the_cap_without_converging_and_says_so(self):
        run_story, propose = self._run([0.5, 0.5, 0.5])
        report = loop.calibrate(self.config, self.derived, self.agent,
                                ["one", "two", "three", "four"], run_story, propose)
        self.assertEqual(report["stop"], loop.Stop.CAP_REACHED)
        self.assertFalse(report["converged"])
        self.assertEqual(report["runs"], 3)

    def test_disabled_never_runs(self):
        self.config["learning"]["enabled"] = False
        run_story, propose = self._run([0.5])
        report = loop.calibrate(self.config, self.derived, self.agent,
                                ["one"], run_story, propose)
        self.assertEqual(report["stop"], loop.Stop.DISABLED)
        self.assertEqual(report["runs"], 0)

    def test_an_invalid_candidate_stops_the_loop_rather_than_being_written(self):
        run_story, _ = self._run([0.5, 0.5])
        report = loop.calibrate(self.config, self.derived, self.agent, ["one", "two"],
                                run_story, lambda *_: "**Write 380 words.**")
        self.assertEqual(report["stop"], loop.Stop.NO_VALID_CANDIDATE)
        self.assertEqual(prompt_block.read(self.agent)[0], "v1")

    def test_results_are_saved_per_prompt(self):
        run_story, propose = self._run([0.5, 0.5, 0.1])
        loop.calibrate(self.config, self.derived, self.agent,
                       ["one", "two", "three"], run_story, propose)
        for story_id in ("one", "two", "three"):
            path = os.path.join(self.config["paths"]["stories_root"], story_id,
                                self.config["paths"]["calibration"])
            self.assertTrue(os.path.exists(path), path)
        collected = ledger.collect(self.config["paths"]["stories_root"],
                                   self.config["paths"]["calibration"])
        self.assertEqual(sorted(ledger.by_variant(collected)), ["v1", "v2", "v3"])

    def test_a_markdown_report_is_written_for_every_phrasing(self):
        """Each file carries the rule 2 that was in force, the flows run under it
        and the share of pages that failed the length check."""
        run_story, propose = self._run([0.5, 0.5, 0.1])
        loop.calibrate(self.config, self.derived, self.agent,
                       ["one", "two", "three"], run_story, propose)
        loops = self.config["paths"]["loops_dir"]
        self.assertEqual(sorted(os.listdir(loops)),
                         ["summary.md", "v1.md", "v2.md", "v3.md"])

        first = io.open(os.path.join(loops, "v1.md"), encoding="utf-8").read()
        self.assertIn("Write to the target length, not past it.", first)
        self.assertIn("50.0%", first)
        self.assertIn("**1 flow(s).**", first)
        self.assertIn("Above the ceiling", first)

        last = io.open(os.path.join(loops, "v3.md"), encoding="utf-8").read()
        self.assertIn("10.0%", last)
        self.assertIn("At or below the ceiling", last)

        summary = io.open(os.path.join(loops, "summary.md"), encoding="utf-8").read()
        for variant in ("v1", "v2", "v3"):
            self.assertIn("[`%s`](%s.md)" % (variant, variant), summary)

    def test_reports_are_a_rendering_and_rebuild_from_the_workspaces(self):
        run_story, propose = self._run([0.5, 0.1])
        loop.calibrate(self.config, self.derived, self.agent,
                       ["one", "two"], run_story, propose)
        loops = self.config["paths"]["loops_dir"]
        shutil.rmtree(loops)
        loop.render(self.config, self.config["paths"]["stories_root"],
                    self.config["learning"]["max_first_attempt_length_failure_rate"], "rebuilt")
        self.assertEqual(sorted(os.listdir(loops)), ["summary.md", "v1.md", "v2.md"])

    def test_a_run_below_the_floor_writes_nothing(self):
        """SR-02: a short run is reported and contributes no observation."""
        def run_story(story_id, config):
            return {"attempts": [attempt(1, 1, 400, ["length"])], "repairs": 0}
        report = loop.calibrate(self.config, self.derived, self.agent, ["one"],
                                run_story, lambda *_: "**Stop at the target.**")
        self.assertEqual(report["stop"], loop.Stop.TOO_SHORT)
        path = os.path.join(self.config["paths"]["stories_root"], "one",
                            self.config["paths"]["calibration"])
        self.assertFalse(os.path.exists(path))


class TestConfigInvariants(unittest.TestCase):
    """Self-improvement 3, on the same path as the invariants of functional 2.3."""

    def setUp(self):
        self.config = derive.load(os.path.join(ROOT, "config.json"))
        self.derived = derive.derive(self.config)

    def test_the_shipped_configuration_is_valid(self):
        self.assertEqual(derive.validate(self.config, self.derived), [])

    def test_every_learning_bound_is_checked(self):
        for key, bad in (("max_first_attempt_length_failure_rate", 1),
                         ("max_calibration_runs", 0),
                         ("min_pages_per_observation", 0),
                         ("max_length_block_words", 0),
                         ("epoch_label", "  ")):
            config = derive.load(os.path.join(ROOT, "config.json"))
            config["learning"][key] = bad
            problems = derive.validate(config, self.derived)
            self.assertTrue(any(key in problem for problem in problems), key)

    def test_the_shipped_prompt_block_is_valid(self):
        """V-13: no configuration literal in an agent definition."""
        path = os.path.join(ROOT, ".claude", "agents", "page-writer.md")
        _, instruction = prompt_block.read(path)
        ceiling = self.config["learning"]["max_length_block_words"]
        self.assertEqual(prompt_block.validate(instruction, ceiling), [])


if __name__ == "__main__":
    unittest.main()
