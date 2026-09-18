"""B4 — mechanical validation, in code. FR-10 length, FR-11 roster, structure.

Measured, never reported (FR-25). The roster check is deliberately permissive:
any name the bible declares may appear anywhere, because a word matcher cannot
tell a mention from an entrance (TR-14e). That half of FR-11 is K7 and belongs
to consistency-checker.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ui.derive import load, derive


def count_words(prose):
    return len(re.findall(r"\b[\w'’-]+\b", prose))


def roster(story_root, paths):
    names = {}
    directory = os.path.join(story_root, paths["characters_dir"])
    for f in sorted(os.listdir(directory)):
        text = open(os.path.join(directory, f), encoding="utf-8").read()
        cid = re.search(r"^id:\s*(\S+)", text, re.M)
        name = re.search(r"^name:\s*(.+)$", text, re.M)
        if cid and name:
            names[cid.group(1)] = name.group(1).strip()
    return names


def validate(story_id, page, prose, config=None, derived=None):
    config = config or load("config.json")
    derived = derived or derive(config, story_id)
    root, paths = derived["story_root"], config["paths"]
    rejected, detail = [], {}

    # FR-10 — length.
    words = count_words(prose)
    band = derived["word_band"]
    detail["words"] = words
    if not band["min"] <= words <= band["max"]:
        rejected.append("length")
        detail["length"] = ("%d words, outside the accepted band %d to %d (target %d), %s by %d"
                            % (words, band["min"], band["max"], band["target"],
                               "over" if words > band["max"] else "under",
                               words - band["max"] if words > band["max"] else band["min"] - words))

    # FR-11 — roster. Permissive by design: only names the bible does not declare.
    declared = roster(root, paths)
    known = {n.lower() for n in declared.values()}
    known |= {part.lower() for n in declared.values() for part in n.split()}
    capitalised = set(re.findall(r"(?<![.!?“\"]\s)(?<!^)\b([A-Z][a-z]{2,})\b", prose, re.M))
    stop = {"The", "And", "But", "He", "She", "They", "It", "His", "Her", "Their", "That", "This",
            "When", "Then", "There", "Strait", "Glass", "Ferry", "Not", "For", "You", "What", "Why",
            "How", "All", "One", "Now", "Nothing", "Even", "Only", "Still", "Perhaps", "Yes", "No"}
    unknown = sorted(n for n in capitalised - stop if n.lower() not in known)
    detail["unknown_capitalised"] = unknown

    # Structure — TR-08: prose only, nothing the orchestrator adds.
    problems = []
    if prose.lstrip().startswith("---"):
        problems.append("emits frontmatter")
    if re.search(r"^#{1,6}\s", prose, re.M):
        problems.append("emits a heading")
    if re.search(r"^\s*(page|p\.)\s*\d+\s*$", prose, re.M | re.I):
        problems.append("emits a page number")
    if re.search(r"^\s*(\*{3}|-{3,}|#{3,})\s*$", prose, re.M):
        problems.append("emits a scene marker")
    if problems:
        rejected.append("structure")
        detail["structure"] = "; ".join(problems)

    return rejected, detail


if __name__ == "__main__":
    story, page, path = sys.argv[1], int(sys.argv[2]), sys.argv[3]
    prose = open(path, encoding="utf-8").read()
    rejected, detail = validate(story, page, prose)
    print(json.dumps({"page": page, "rejected": rejected, **detail}, indent=2))
    sys.exit(1 if rejected else 0)
