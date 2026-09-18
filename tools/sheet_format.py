"""Technical specification section 4: sheet format, checked at the A6 gate.

Separate from a6_gate.py only so that the regexes live in one place.
FR-02 needs the arc machine-readable because the Phase C arc audit (C2)
compares the declared final state against the logged one in code.
"""
import os
import re

FENCE = re.compile(r"^---\r?\n(.*?)\r?\n---\r?\n(.*)$", re.S)
ARC = re.compile(r"\{\s*from\s*:.+,\s*to\s*:.+\}")

CHARACTER_FIELDS = ("id", "name", "role", "desire", "fear", "arc")
CHARACTER_BODY = ("Appearance", "Voice")
SETTING_FIELDS = ("id", "name")
SETTING_BODY = ("Appearance", "Atmosphere", "Function")


def _split(path):
    text = open(path, encoding="utf-8").read()
    match = FENCE.match(text)
    return (match.group(1), match.group(2)) if match else (None, text)


def _check(path, name, fields, body_labels, fail):
    head, body = _split(path)
    if head is None:
        fail.append("section-4 %s has no `---` fenced frontmatter" % name)
        head = ""
    for field in fields:
        if not re.search(r"^%s:" % field, head, re.M):
            fail.append("section-4 %s frontmatter has no `%s:` field" % (name, field))
    for label in body_labels:
        if "**%s.**" % label not in body:
            fail.append("section-4 %s body has no `**%s.**` field" % (name, label))
    return head


def check(staging, fail):
    for name in sorted(os.listdir(os.path.join(staging, "characters"))):
        head = _check(os.path.join(staging, "characters", name), name,
                      CHARACTER_FIELDS, CHARACTER_BODY, fail)
        arc = re.search(r"^arc:(.*)$", head, re.M)
        if arc and not ARC.search(arc.group(1)):
            fail.append(
                "FR-02 %s arc is %r; it must be `{from: <initial state>, to: <final state>}` "
                "so that the Phase C arc audit can compare the declared final state against "
                "the logged one in code" % (name, arc.group(1).strip()))
    for name in sorted(os.listdir(os.path.join(staging, "settings"))):
        _check(os.path.join(staging, "settings", name), name,
               SETTING_FIELDS, SETTING_BODY, fail)
