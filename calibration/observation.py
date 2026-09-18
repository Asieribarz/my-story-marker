"""What one run measured about its own page lengths.

Self-improvement specification 4.1. One observation per run, written into that
run's own workspace and never anywhere else: a run reads across workspaces and
writes only inside its own (FR-45).

The numbers come from per-attempt records. The state record of functional 4.2
carries `retries` but not what each attempt was rejected *for*, which is why
the metric is not computable from the log as it stands (SR-01); this module
defines the shape that closes that gap:

    {"page": 7, "attempt": 1, "words": 412, "rejected_by": ["length"]}

`rejected_by` is empty when the attempt was accepted, and otherwise names the
mechanical check ("length", "roster", "structure") or the consistency checks
("K1" ... "K7") that rejected it.
"""

import io
import json
import os

LENGTH = "length"
CONSISTENCY = tuple("K%d" % n for n in range(1, 8))


def first_attempts(attempts):
    """One record per page, the attempt that measures the instruction as written."""
    firsts = {}
    for record in attempts:
        if record.get("attempt") == 1:
            firsts[record["page"]] = record
    return [firsts[page] for page in sorted(firsts)]


def measure(attempts, band, epoch, repairs=0, instruction=None):
    """Build the observation. Every figure is executed here, never asserted."""
    firsts = first_attempts(attempts)
    pages = len(firsts)

    # Length failure: either marked as rejected, or words outside band (too short or too long)
    length_failures = [
        r["page"] for r in firsts
        if LENGTH in (r.get("rejected_by") or [])
        or (isinstance(r.get("words"), int) and (r["words"] < band["min"] or r["words"] > band["max"]))
    ]
    consistency_failures = [
        r["page"] for r in firsts
        if any(check in CONSISTENCY for check in (r.get("rejected_by") or []))
    ]

    counted = [r for r in firsts if isinstance(r.get("words"), int)]
    uncounted = [r["page"] for r in firsts if not isinstance(r.get("words"), int)]
    # SR-11: a page with no word count is not a page of zero words.
    mean_words = sum(r["words"] for r in counted) / len(counted) if counted else None

    target = band["target"]
    return {
        "epoch": dict(epoch),
        # The wording in force, so a report is rebuildable from the workspaces
        # alone and no variant has to be guessed at.
        "instruction": instruction,
        "asked": target,
        "band": {"min": band["min"], "max": band["max"]},
        "pages": pages,
        "first_attempt_length_failures": len(length_failures),
        "length_failure_pages": length_failures,
        "rate": (len(length_failures) / pages) if pages else None,
        "mean_words": mean_words,
        "bias": (mean_words / target) if mean_words and target else None,
        "pages_without_word_count": uncounted,
        # Guards: measured, reported, never optimised (self-improvement 2.3).
        "first_attempt_consistency_rejections": len(consistency_failures),
        "consistency_rate": (len(consistency_failures) / pages) if pages else None,
        "continuity_repairs": repairs,
    }


def write(path, observation):
    """Atomic, as every write in this system is (TR-05)."""
    directory = os.path.dirname(path)
    if directory and not os.path.isdir(directory):
        os.makedirs(directory)
    temporary = path + ".tmp"
    with io.open(temporary, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(observation, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    os.replace(temporary, path)
    return path


def read(path):
    if not os.path.exists(path):
        return None
    with io.open(path, encoding="utf-8") as handle:
        return json.load(handle)
