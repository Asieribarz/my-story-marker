"""The loop reports: one Markdown file per length instruction that was tried.

`paths.loops_dir` sits beside `paths.stories_root` at the repository root, and
is the second path in the file that is not resolved against a story workspace.
That is deliberate and it is bounded: what is written here is a **rendering**,
rebuilt from the calibration observations of each workspace, never a source of
truth. The ledger itself stays a projection (self-improvement 4.2); this is the
same projection written down so that a person can read it, in the way the
manuscript is rebuilt from `pages/` and never edited in place (FR-29).

Delete the folder and `python -m calibration.cli report` restores it exactly.

One file per variant, named for it, carrying what the loop is judged on: the
instruction that was in force, how many flows ran under it, and the share of
pages whose first attempt failed the length check in each.
"""

import io
import os

from . import ledger as ledger_module


def _percentage(value):
    return "-" if value is None else "%.1f%%" % (value * 100)


def _number(value, places=1):
    if value is None:
        return "-"
    return ("%%.%df" % places) % value


def variant_document(variant, instruction, records, ceiling):
    """`records` is a list of (story_id, observation), oldest first."""
    rates = [record["rate"] for _, record in records]
    biases = [record["bias"] for _, record in records]
    mean_rate = ledger_module.mean(rates)

    lines = []
    lines.append("# Length instruction `%s`" % variant)
    lines.append("")
    lines.append("## The rule 2 that was in force")
    lines.append("")
    lines.append("```markdown")
    lines.extend(instruction.splitlines() or [""])
    lines.append("```")
    lines.append("")
    lines.append("## Flows run under it")
    lines.append("")
    lines.append("**%s flow(s).** Ceiling for the length failure rate: %s."
                 % (len(records), _percentage(ceiling)))
    lines.append("")
    lines.append("| # | Story | Pages | First-attempt length failures | Rate | Mean words | Bias |")
    lines.append("|---|---|---|---|---|---|---|")
    for index, (story_id, record) in enumerate(records, start=1):
        lines.append("| %d | `%s` | %s | %s | %s | %s | %s |" % (
            index, story_id, record["pages"],
            record["first_attempt_length_failures"],
            _percentage(record["rate"]),
            _number(record["mean_words"]),
            _number(record["bias"], 3),
        ))
    lines.append("")
    lines.append("**Mean rate across these flows: %s.** Mean bias: %s."
                 % (_percentage(mean_rate), _number(ledger_module.mean(biases), 3)))
    lines.append("")

    if mean_rate is None:
        verdict = "No flow has been measured under this instruction yet."
    elif mean_rate <= ceiling:
        verdict = ("**At or below the ceiling.** This instruction met the criterion and the "
                   "loop stops here.")
    else:
        verdict = ("**Above the ceiling.** This instruction did not meet the criterion, and the "
                   "loop rewrote it.")
    lines.append("## Verdict")
    lines.append("")
    lines.append(verdict)
    lines.append("")

    failures = [(story_id, record["length_failure_pages"])
                for story_id, record in records if record["length_failure_pages"]]
    if failures:
        lines.append("Pages whose first attempt was over or under the band:")
        lines.append("")
        for story_id, pages in failures:
            lines.append("- `%s`: %s" % (story_id, ", ".join(str(page) for page in pages)))
        lines.append("")

    lines.append("## Guards")
    lines.append("")
    lines.append("Measured, never optimised (self-improvement 2.3). A rewrite that improved "
                 "length by damaging these is not an improvement.")
    lines.append("")
    lines.append("| Story | First-attempt consistency rejections | Continuity repairs |")
    lines.append("|---|---|---|")
    for story_id, record in records:
        lines.append("| `%s` | %s (%s) | %s |" % (
            story_id, record["first_attempt_consistency_rejections"],
            _percentage(record["consistency_rate"]), record["continuity_repairs"]))
    lines.append("")
    return "\n".join(lines)


def summary_document(rows, ceiling, stop):
    lines = []
    lines.append("# Calibration of the length instruction")
    lines.append("")
    lines.append("Every phrasing of rule 2 of `page-writer.md` that has been tried, in order, "
                 "with the share of pages whose first attempt failed the length check.")
    lines.append("")
    lines.append("Ceiling: **%s**. Stop condition now: **%s**." % (_percentage(ceiling), stop))
    lines.append("")
    lines.append("| Variant | Flows | Mean rate | Mean bias | Instruction |")
    lines.append("|---|---|---|---|---|")
    for row in rows:
        lines.append("| [`%s`](%s.md) | %s | %s | %s | %s |" % (
            row["variant"], row["variant"], row["flows"],
            _percentage(row["mean_rate"]), _number(row["mean_bias"], 3),
            row["instruction"].replace("|", "\\|").replace("\n", " "),
        ))
    lines.append("")
    lines.append("Each file is a rendering of the calibration observations held in the "
                 "workspaces under `paths.stories_root`; nothing here is a source of truth, "
                 "and `python -m calibration.cli report` rebuilds all of it.")
    lines.append("")
    return "\n".join(lines)


def write(path, text):
    directory = os.path.dirname(path)
    if directory and not os.path.isdir(directory):
        os.makedirs(directory)
    temporary = path + ".tmp"
    with io.open(temporary, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    os.replace(temporary, path)
    return path


def rebuild(loops_dir, collected, instructions, ceiling, stop):
    """Regenerate every report from the observations on disk.

    `instructions` maps a variant to the instruction text that produced it; a
    variant with no recorded text is reported as unknown rather than guessed.
    """
    grouped = ledger_module.by_variant(collected)
    rows, written = [], []
    for variant in sorted(grouped, key=_variant_order):
        records = grouped[variant]
        instruction = instructions.get(variant, "_not recorded_")
        written.append(write(os.path.join(loops_dir, "%s.md" % variant),
                             variant_document(variant, instruction, records, ceiling)))
        rows.append({
            "variant": variant,
            "flows": len(records),
            "mean_rate": ledger_module.mean([r["rate"] for _, r in records]),
            "mean_bias": ledger_module.mean([r["bias"] for _, r in records]),
            "instruction": instruction,
        })
    written.append(write(os.path.join(loops_dir, "summary.md"),
                         summary_document(rows, ceiling, stop)))
    return written


def _variant_order(variant):
    """`v2` before `v10`, and anything unparseable last, by name."""
    if variant.startswith("v") and variant[1:].isdigit():
        return (0, int(variant[1:]), "")
    return (1, 0, variant)
