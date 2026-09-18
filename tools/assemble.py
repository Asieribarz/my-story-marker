"""assemble(N) — technical specification section 6. Deterministic, no model.

TR-10d is the rule this file exists to honour: the Length section carries
derived.word_band and NO instruction. What the writer does with those numbers
is rule 2 of page-writer.md and is written there only.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ui.derive import load, derive


def read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read().strip()


def records(state_log):
    """The state log, replayed. A superseding record replaces the one it names."""
    if not os.path.exists(state_log):
        return []
    rows = [json.loads(line) for line in open(state_log, encoding="utf-8") if line.strip()]
    superseded = {r["supersedes"] for r in rows if r.get("supersedes") is not None}
    return [r for r in rows if r["page"] not in superseded or r.get("supersedes") is not None]


def current_states(rows, character_ids):
    """TR-11: the last record that mentions each character, not the sheet."""
    state = {}
    for row in rows:
        for cid, value in (row.get("states") or {}).items():
            state[cid] = value
    return {cid: state.get(cid) for cid in character_ids}


def final_paragraph(path):
    if not os.path.exists(path):
        return None
    body = read(path)
    if body.startswith("---"):
        body = body.split("---", 2)[-1].strip()
    paragraphs = [p.strip() for p in body.split("\n\n") if p.strip()]
    return paragraphs[-1] if paragraphs else None


def assemble(story_id, page, config=None, derived=None):
    config = config or load("config.json")
    derived = derived or derive(config, story_id)
    root, paths = derived["story_root"], config["paths"]
    join = lambda key: os.path.join(root, paths[key])

    beats = json.load(open(join("beats"), encoding="utf-8"))
    beat = next(b for b in beats if b["page"] == page)

    chars, sets_ = beat.get("characters") or [], beat.get("settings") or []
    assert len(chars) <= config["context"]["max_characters_per_page"], "I-7 cast ceiling"
    assert len(sets_) <= config["context"]["max_settings_per_page"], "I-7 setting ceiling"

    sheet = lambda d, i: read(os.path.join(join(d), next(
        f for f in sorted(os.listdir(join(d))) if f.startswith(i + "-"))))

    rows = records(join("state_log"))
    states = current_states(rows, chars)

    # Digests of chapters closed before this one.
    digests = []
    for ch in range(1, beat["chapter"]):
        p = os.path.join(join("chapter_digests_dir"), "%02d.md" % ch)
        if os.path.exists(p):
            digests.append((ch, read(p)))

    # FR-41: the recent summaries are kept even where their chapter is digested.
    window = config["context"]["verbatim_summary_window"]
    recent = [(r["page"], r["summary"]) for r in rows if r["page"] < page][-window:]

    # TR-12: a page that opens a chapter gets the previous digest in place of a bridge.
    opens_chapter = page == 1 or next(b for b in beats if b["page"] == page - 1)["chapter"] != beat["chapter"]
    bridge = None
    if config["context"]["include_bridge_paragraph"] and page > 1 and not opens_chapter:
        bridge = final_paragraph(os.path.join(join("pages_dir"), "%02d.md" % (page - 1)))

    out = []
    out.append("## Voice\n\n- tone: %s\n- audience: %s\n- language: %s"
               % (config["story"]["tone"], config["story"]["audience"], config["story"]["language"]))
    out.append("## World rules\n\n%s" % read(join("world_rules")))

    block = []
    for cid in chars:
        text, state = sheet("characters_dir", cid), states.get(cid)
        block.append(text + ("\n\n**Current state (from the state log, not the sheet).** %s" % state
                             if state else "\n\n**Current state.** As the sheet declares; this character has not appeared yet."))
    for sid in sets_:
        block.append(sheet("settings_dir", sid))
    out.append("## Sheets\n\n" + "\n\n---\n\n".join(block))

    out.append("## This page\n\n- page: %d of %d\n- chapter: %d, %r\n- act: %s\n- anchor page: %s\n"
               "- objective: %s\n- closing hook: %s"
               % (page, config["organization"]["pages_total"], beat["chapter"], beat["chapter_title"],
                  beat["act"], "yes" if beat.get("anchor") else "no", beat["objective"], beat["hook"]))

    before = []
    for ch, text in digests:
        before.append("**Digest of chapter %d.** %s" % (ch, text))
    for n, summary in recent:
        before.append("**Page %d.** %s" % (n, summary))
    if bridge:
        before.append("**Final paragraph of page %d — continue directly from this.**\n\n%s" % (page - 1, bridge))
    elif opens_chapter and digests:
        before.append("This page opens a chapter: the digest above stands in place of a bridging paragraph.")
    out.append("## Before\n\n" + ("\n\n".join(before) if before else "Nothing precedes this page."))

    band = derived["word_band"]
    # TR-10d: the target and the band, and no instruction.
    out.append("## Length\n\n- target: %d words\n- accepted band: %d to %d words"
               % (band["target"], band["min"], band["max"]))

    return "\n\n".join(out) + "\n", beat


if __name__ == "__main__":
    story, page = sys.argv[1], int(sys.argv[2])
    context, _ = assemble(story, page)
    cfg = load("config.json")
    der = derive(cfg, story)
    run = sys.argv[3] if len(sys.argv) > 3 else None
    if run:
        out = os.path.join(der["story_root"], cfg["paths"]["runs_dir"], run, "ctx-%02d.md" % page)
        open(out, "w", encoding="utf-8").write(context)
        print("wrote", out, "(%d chars)" % len(context))
    print(context)
