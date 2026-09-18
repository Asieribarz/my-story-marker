"""The calibration ledger: a projection, never a file.

Self-improvement specification 4.2. The ledger is obtained by reading the
observation of every workspace under `paths.stories_root` and keeping those
whose epoch matches the one in force. Nothing writes it, for the same reason
the thread register of functional 4.2 is a replay rather than a stored file: a
shared file is a value two runs can disagree about, and it would be the first
thing in this design to live outside a story workspace.

Reading across workspaces is permitted; writing across them is not.
"""

import os

from . import observation as observation_module


KEYS = ("epoch_label", "target_words", "length_tolerance", "prompt_variant", "prompt_digest")


def epoch_of(config, variant, block_digest):
    """What makes two runs comparable: the campaign, the band, and the wording
    that was in force (self-improvement 4.5)."""
    return {
        "epoch_label": config["learning"]["epoch_label"],
        "target_words": config["page"]["target_words"],
        "length_tolerance": config["page"]["length_tolerance"],
        "prompt_variant": variant,
        "prompt_digest": block_digest,
    }


def same_epoch(left, right):
    return all(left.get(key) == right.get(key) for key in KEYS)


def collect(stories_root, calibration_path):
    """Every observation on disk, with the workspace that produced it."""
    found = []
    if not os.path.isdir(stories_root):
        return found
    for story_id in sorted(os.listdir(stories_root)):
        workspace = os.path.join(stories_root, story_id)
        if not os.path.isdir(workspace):
            continue
        record = observation_module.read(os.path.join(workspace, calibration_path))
        if record is not None:
            found.append((story_id, record))
    return found


def for_epoch(collected, epoch):
    """The ledger proper, plus what was excluded and why (SR-10)."""
    kept, excluded = [], []
    for story_id, record in collected:
        if same_epoch(record.get("epoch") or {}, epoch):
            kept.append((story_id, record))
        else:
            excluded.append((story_id, _difference(record.get("epoch") or {}, epoch)))
    return kept, excluded


def _difference(observed, epoch):
    parts = []
    for key in KEYS:
        if observed.get(key) != epoch.get(key):
            parts.append("%s %s != %s" % (key, observed.get(key), epoch.get(key)))
    return "; ".join(parts) or "epoch differs"


def by_variant(collected):
    """Every observation grouped by the prompt variant that produced it, which is
    what 'the results for each prompt' means once a variant is part of the epoch."""
    grouped = {}
    for story_id, record in collected:
        variant = (record.get("epoch") or {}).get("prompt_variant", "unknown")
        grouped.setdefault(variant, []).append((story_id, record))
    return grouped


def mean(values):
    present = [value for value in values if value is not None]
    return sum(present) / len(present) if present else None
