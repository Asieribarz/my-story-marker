"""Derivation and validation of config.json.

Implements functional specification section 2.2 (derivation) and 2.3
(invariants). Derived values are computed here on every load and are never
written back into config.json (TR-03b, FR-36).
"""

import json
import math
import os


class ConfigError(ValueError):
    """An invariant of functional section 2.3 does not hold."""


def load(config_path):
    with open(config_path, encoding="utf-8") as handle:
        return json.load(handle)


def chapter_sizes(pages_total, chapters):
    base, extra = divmod(pages_total, chapters)
    return [base + 1] * extra + [base] * (chapters - extra)


def chapter_spans(sizes):
    spans, first = [], 1
    for size in sizes:
        spans.append({"first": first, "last": first + size - 1, "pages": size})
        first += size
    return spans


def act_spans(pages_total, proportions):
    """Largest remainder, ties in declaration order, every act at least one page."""
    names = list(proportions)
    exact = [pages_total * proportions[name] for name in names]
    counts = [max(1, math.floor(value)) for value in exact]
    remaining = pages_total - sum(counts)
    order = sorted(range(len(names)), key=lambda i: (-(exact[i] - math.floor(exact[i])), i))
    index = 0
    while remaining > 0:
        counts[order[index % len(order)]] += 1
        remaining -= 1
        index += 1
    while remaining < 0:
        for i in sorted(range(len(names)), key=lambda i: -counts[i]):
            if counts[i] > 1:
                counts[i] -= 1
                remaining += 1
                break
        else:
            break
    spans, first = [], 1
    for name, count in zip(names, counts):
        spans.append({"act": name, "first": first, "last": first + count - 1, "pages": count})
        first += count
    return spans


def derive(config, story_id=None):
    organization = config["organization"]
    pages_total = organization["pages_total"]
    supersessions = []

    chapters = organization.get("chapters")
    per_chapter = organization.get("pages_per_chapter")
    if chapters and per_chapter:
        implied = math.ceil(pages_total / per_chapter)
        if implied != chapters:
            # FR-37: chapters wins, and the superseded value is reported.
            supersessions.append(
                "organization.pages_per_chapter = %s implies %s chapters; "
                "organization.chapters = %s wins and supersedes it."
                % (per_chapter, implied, chapters)
            )
    elif not chapters and per_chapter:
        chapters = math.ceil(pages_total / per_chapter)
    elif not chapters:
        chapters = 1

    sizes = chapter_sizes(pages_total, chapters)
    acts = act_spans(pages_total, organization["act_proportions"])

    anchors = organization.get("anchor_pages")
    if anchors == "auto" or anchors is None:
        development = next((a for a in acts if a["act"] == "development"), acts[len(acts) // 2])
        middle = (development["first"] + development["last"]) // 2
        anchors = sorted({development["first"], middle, development["last"]})

    derived = {
        "chapters": chapters,
        "chapter_sizes": sizes,
        "chapter_spans": chapter_spans(sizes),
        "acts": [a["act"] for a in acts],
        "act_spans": acts,
        "anchor_pages": list(anchors),
        "word_band": word_band(config["page"]),
        "supersessions": supersessions,
    }
    if story_id:
        derived["story_root"] = os.path.join(config["paths"]["stories_root"], story_id)
    return derived


def word_band(page):
    target, tolerance = page["target_words"], page["length_tolerance"]
    return {"min": round(target * (1 - tolerance)), "max": round(target * (1 + tolerance))}


def validate(config, derived):
    """Functional section 2.3. Returns the list of violations; empty means valid."""
    problems = []
    organization = config["organization"]
    pages_total = organization["pages_total"]

    if not isinstance(pages_total, int) or pages_total < 1:
        problems.append("2.3.1 organization.pages_total must be an integer of at least 1.")
    if not 1 <= derived["chapters"] <= max(pages_total, 1):
        problems.append(
            "2.3.1 derived chapter count %s lies outside [1, %s]."
            % (derived["chapters"], pages_total)
        )

    proportions = organization["act_proportions"]
    if any(value <= 0 for value in proportions.values()):
        problems.append("2.3.2 every organization.act_proportions value must be positive.")
    if abs(sum(proportions.values()) - 1) > 1e-9:
        problems.append("2.3.2 organization.act_proportions must sum to 1.")
    if pages_total < len(proportions):
        problems.append(
            "2.3.2 organization.pages_total must be at least the number of acts (%s)."
            % len(proportions)
        )

    if organization.get("anchor_pages") not in ("auto", None):
        for page in organization["anchor_pages"]:
            if not 1 <= page <= pages_total:
                problems.append("2.3.3 anchor page %s lies outside [1, %s]." % (page, pages_total))

    bible, context, page = config["bible"], config["context"], config["page"]
    if bible["world_rules_min"] > bible["world_rules_max"]:
        problems.append("2.3.4 bible.world_rules_min must not exceed bible.world_rules_max.")
    if not 0 < page["length_tolerance"] < 1:
        problems.append("2.3.5 page.length_tolerance must lie in (0, 1).")
    if bible["max_characters"] < context["max_characters_per_page"]:
        problems.append(
            "2.3.6 bible.max_characters must be at least context.max_characters_per_page."
        )
    if bible["max_settings"] < context["max_settings_per_page"]:
        problems.append("2.3.6 bible.max_settings must be at least context.max_settings_per_page.")

    for key, value in config["paths"].items():
        if key == "stories_root":
            continue
        if os.path.isabs(value) or value.startswith("..") or ".." in value.split("/"):
            # I-9 / FR-45: no path may escape the story workspace.
            problems.append("2.3.7 paths.%s must resolve inside the story workspace." % key)

    return problems
