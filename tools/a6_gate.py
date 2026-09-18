"""A6 gate, arithmetic half. Functional 5 A6, FR-22, FR-04, FR-05, FR-28, I-7.

Executed, never asserted. The anchor-reversal judgement (FR-27) is not here:
it is a separate delegated call, which is OI-12.
"""
import json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ui.derive import load, derive
import sheet_format


def gate(staging, config, derived):
    fail = []
    beats = json.load(open(os.path.join(staging, "beats.json"), encoding="utf-8"))
    total = config["organization"]["pages_total"]
    ctx, bible_bounds = config["context"], config["bible"]

    # FR-22: every page has exactly one beat entry.
    pages = [b["page"] for b in beats]
    for n in range(1, total + 1):
        if pages.count(n) != 1:
            fail.append("FR-22 page %d has %d beat entries, expected exactly 1" % (n, pages.count(n)))
    for n in pages:
        if not 1 <= n <= total:
            fail.append("FR-22 beat entry for page %d lies outside [1, %d]" % (n, total))

    # FR-22: chapter n holds derived.chapter_sizes[n] pages, and they tile.
    for span, size in zip(derived["chapter_spans"], derived["chapter_sizes"]):
        got = sorted(b["page"] for b in beats if b["chapter"] == derived["chapter_spans"].index(span) + 1)
        want = list(range(span["first"], span["last"] + 1))
        if got != want:
            fail.append("FR-22 chapter %d holds pages %s, expected %s (size %d)"
                        % (derived["chapter_spans"].index(span) + 1, got, want, size))

    # FR-28: every chapter has a title, on every entry of that chapter.
    for ch in range(1, derived["chapters"] + 1):
        titles = {b.get("chapter_title") for b in beats if b["chapter"] == ch}
        if len(titles) != 1 or not next(iter(titles), "").strip():
            fail.append("FR-28 chapter %d carries titles %s, expected exactly one non-empty" % (ch, titles))

    # Act boundaries fall where derived.act_spans puts them.
    act_of = {}
    for span in derived["act_spans"]:
        for n in range(span["first"], span["last"] + 1):
            act_of[n] = span["act"]
    for b in beats:
        if b.get("act") != act_of.get(b["page"]):
            fail.append("act boundary: page %d declares act %r, derivation puts it in %r"
                        % (b["page"], b.get("act"), act_of.get(b["page"])))

    # Anchor flags match derived.anchor_pages (the flag; the reversal is judged elsewhere).
    for b in beats:
        want = b["page"] in derived["anchor_pages"]
        if bool(b.get("anchor")) != want:
            fail.append("anchor flag: page %d has anchor=%r, derivation says %r" % (b["page"], b.get("anchor"), want))

    # FR-04: unique one-line objective and a closing hook.
    seen = {}
    for b in beats:
        obj, hook = (b.get("objective") or "").strip(), (b.get("hook") or "").strip()
        if not obj:
            fail.append("FR-04 page %d has no objective" % b["page"])
        if "\n" in obj:
            fail.append("FR-04 page %d objective is not one line" % b["page"])
        if not hook:
            fail.append("FR-04 page %d has no closing hook" % b["page"])
        if obj in seen:
            fail.append("FR-04 page %d repeats the objective of page %d" % (b["page"], seen[obj]))
        seen[obj] = b["page"]

    # FR-05 + I-7: declared cast and settings, and the per-page ceilings.
    cfiles = {f.split("-")[0] for f in os.listdir(os.path.join(staging, "characters"))}
    sfiles = {f.split("-")[0] for f in os.listdir(os.path.join(staging, "settings"))}
    used_c, used_s = set(), set()
    for b in beats:
        cs, ss = b.get("characters") or [], b.get("settings") or []
        if not cs:
            fail.append("FR-05 page %d declares no characters" % b["page"])
        if len(cs) > ctx["max_characters_per_page"]:
            fail.append("I-7 page %d declares %d characters, ceiling is %d"
                        % (b["page"], len(cs), ctx["max_characters_per_page"]))
        if len(ss) > ctx["max_settings_per_page"]:
            fail.append("I-7 page %d declares %d settings, ceiling is %d"
                        % (b["page"], len(ss), ctx["max_settings_per_page"]))
        for c in cs:
            if c not in cfiles:
                fail.append("FR-05 page %d declares character %r with no sheet" % (b["page"], c))
        for s in ss:
            if s not in sfiles:
                fail.append("FR-05 page %d declares setting %r with no sheet" % (b["page"], s))
        used_c |= set(cs); used_s |= set(ss)

    for c in cfiles - used_c:
        fail.append("character %s has a sheet but no beat entry uses it" % c)
    for s in sfiles - used_s:
        fail.append("setting %s has a sheet but no beat entry uses it" % s)

    # Bible ceilings.
    if len(cfiles) > bible_bounds["max_characters"]:
        fail.append("bible.max_characters: %d sheets, ceiling %d" % (len(cfiles), bible_bounds["max_characters"]))
    if len(sfiles) > bible_bounds["max_settings"]:
        fail.append("bible.max_settings: %d sheets, ceiling %d" % (len(sfiles), bible_bounds["max_settings"]))

    sheet_format.check(staging, fail)

    # World rules within bounds.
    rules = [l for l in open(os.path.join(staging, "rules.md"), encoding="utf-8").read().splitlines()
             if l.strip() and not l.strip().startswith("#")]
    if not bible_bounds["world_rules_min"] <= len(rules) <= bible_bounds["world_rules_max"]:
        fail.append("world rules: %d, bounds [%d, %d]"
                    % (len(rules), bible_bounds["world_rules_min"], bible_bounds["world_rules_max"]))

    # I-9 / FR-45: nothing staged outside the staging directory.
    root = os.path.abspath(staging)
    for dirpath, _, names in os.walk(staging):
        for n in names:
            if not os.path.abspath(os.path.join(dirpath, n)).startswith(root):
                fail.append("I-9 staged file escapes the staging directory: %s" % n)

    return fail, beats, sorted(cfiles), sorted(sfiles), len(rules)


if __name__ == "__main__":
    story = sys.argv[1]
    cfg = load("config.json")
    der = derive(cfg, story)
    stg = os.path.join(der["story_root"], cfg["paths"]["staging_dir"])
    problems, beats, cs, ss, nrules = gate(stg, cfg, der)
    print("staged: %d beats, %d characters %s, %d settings %s, %d world rules"
          % (len(beats), len(cs), cs, len(ss), ss, nrules))
    if problems:
        print("\nA6 ARITHMETIC HALF: FAIL (%d)" % len(problems))
        for p in problems:
            print("  -", p)
        sys.exit(1)
    print("\nA6 ARITHMETIC HALF: PASS")
