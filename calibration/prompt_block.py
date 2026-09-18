"""The one part of an agent definition calibration may rewrite.

The block is delimited in `.claude/agents/page-writer.md` by

    <!-- calibrated:length <variant> -->
    ...the instruction...
    <!-- /calibrated -->

and nothing outside those markers is ever touched. The variant identifier in
the opening marker is what ties the file to the epoch of the calibration
ledger: an edit that does not bump it makes two different systems look like
one (self-improvement specification 4.3).

No configuration value appears here, and none may appear in the block: the
number the writer aims at arrives in the invocation payload, never in the
prompt (FR-20, FR-47, checklist V-13).
"""

import hashlib
import io
import os
import re

OPEN = re.compile(r"<!--\s*calibrated:length\s+(?P<variant>[A-Za-z0-9_.-]+)\s*-->")
CLOSE = "<!-- /calibrated -->"

# A length instruction that no longer mentions length is the trivial way to
# satisfy a length metric, so the candidate has to still be about length.
LENGTH_WORDS = ("length", "word", "words", "target", "long", "longer", "short", "shorter")

DIGIT = re.compile(r"\d")
TEMPLATE = re.compile(r"\{\{|\}\}")


class BlockError(ValueError):
    """The calibrated block is missing or malformed."""


def _split(text):
    opening = OPEN.search(text)
    if opening is None:
        raise BlockError("no opening <!-- calibrated:length ... --> marker")
    start = opening.end()
    close = text.find(CLOSE, start)
    if close == -1:
        raise BlockError("no closing %s marker after the opening one" % CLOSE)
    return opening, start, close


def read(path):
    """Return (variant, instruction text), the text stripped of its indentation."""
    with io.open(path, encoding="utf-8") as handle:
        text = handle.read()
    opening, start, close = _split(text)
    body = text[start:close]
    lines = [line.strip() for line in body.splitlines() if line.strip()]
    return opening.group("variant"), "\n".join(lines)


def digest(instruction):
    """Content hash of the instruction, so a variant that was edited without
    being renamed can be detected rather than silently averaged in."""
    return hashlib.sha256(instruction.encode("utf-8")).hexdigest()[:12]


def validate(instruction, max_words):
    """Mechanical checks, no model involvement. Returns the list of problems."""
    problems = []
    if not instruction.strip():
        problems.append("the block is empty: a deleted instruction is not a calibrated one.")
    if DIGIT.search(instruction):
        problems.append(
            "the block contains a digit; the target and the band arrive in the payload "
            "and no configuration literal may appear in an agent definition (FR-20, V-13)."
        )
    if TEMPLATE.search(instruction):
        problems.append(
            "the block contains a template placeholder; an agent definition is not rendered, "
            "values reach the agent by payload (FR-47)."
        )
    lowered = instruction.lower()
    if not any(word in lowered for word in LENGTH_WORDS):
        problems.append(
            "the block no longer mentions length, so it is not a length instruction."
        )
    words = len(instruction.split())
    if words > max_words:
        problems.append(
            "the block is %s words against a ceiling of %s; the writer's prompt heads every "
            "page payload as a cacheable prefix (TR-13) and grows the cost of every call."
            % (words, max_words)
        )
    if OPEN.search(instruction) or CLOSE in instruction:
        problems.append("the block contains its own markers.")
    return problems


def write(path, instruction, variant):
    """Replace the block in place, atomically (TR-05). Nothing else in the file moves."""
    with io.open(path, encoding="utf-8") as handle:
        text = handle.read()
    opening, start, close = _split(text)

    # Keep the instruction inside its list item: indent as the closing marker is.
    line_start = text.rfind("\n", 0, close) + 1
    indent = text[line_start:close]
    body = "\n" + "\n".join(indent + line for line in instruction.splitlines()) + "\n" + indent

    head = text[:opening.start()] + "<!-- calibrated:length %s -->" % variant
    updated = head + body + text[close:]

    temporary = path + ".tmp"
    io.open(temporary, "w", encoding="utf-8", newline="\n").write(updated)
    os.replace(temporary, path)
    return updated


def next_variant(variant):
    """`v3` becomes `v4`. A variant that does not follow the pattern gets a suffix."""
    match = re.fullmatch(r"v(\d+)", variant)
    if match:
        return "v%d" % (int(match.group(1)) + 1)
    return variant + ".1"
