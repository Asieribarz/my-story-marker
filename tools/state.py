"""B7 state records, C1-C3 closing audits, C4 manuscript assembly. All code.

Thread replay, arc comparison and chapter balance are replay (FR-19, FR-25):
if they were asserted rather than executed, the run's claims about itself
would be worth nothing.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ui.derive import load, derive
from assemble import records, read


def write_atomic(path, text):
    """TR-05: written to a temporary file and renamed."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        handle.write(text)
    os.replace(tmp, path)


def write_page(root, paths, page, beat, prose, flagged, reasons):
    head = ["---", "page: %d" % page, "chapter: %d" % beat["chapter"],
            "chapter_title: %s" % beat["chapter_title"], "act: %s" % beat["act"],
            "anchor: %s" % ("true" if beat.get("anchor") else "false")]
    if flagged:
        head.append("flagged: true")
        head.append("flag_reason: %s" % "; ".join(reasons))
    head.append("---")
    write_atomic(os.path.join(root, paths["pages_dir"], "%02d.md" % page),
                 "\n".join(head) + "\n\n" + prose.strip() + "\n")


def append_record(root, paths, record):
    path = os.path.join(root, paths["state_log"])
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def arcs(root, paths):
    out = {}
    directory = os.path.join(root, paths["characters_dir"])
    for f in sorted(os.listdir(directory)):
        text = open(os.path.join(directory, f), encoding="utf-8").read()
        cid = re.search(r"^id:\s*(\S+)", text, re.M)
        name = re.search(r"^name:\s*(.+)$", text, re.M)
        arc = re.search(r"^arc:\s*\{\s*from\s*:\s*(.+?)\s*,\s*to\s*:\s*(.+?)\s*\}", text, re.M)
        if cid:
            out[cid.group(1)] = {"name": name.group(1).strip() if name else cid.group(1),
                                 "from": arc.group(1) if arc else None,
                                 "to": arc.group(2) if arc else None}
    return out


def audit(story_id, config=None, derived=None):
    config = config or load("config.json")
    derived = derived or derive(config, story_id)
    root, paths = derived["story_root"], config["paths"]
    rows = records(os.path.join(root, paths["state_log"]))
    beats = json.load(open(os.path.join(root, paths["beats"]), encoding="utf-8"))

    # C1 — open threads, by replay.
    opened, closed = {}, set()
    for r in rows:
        for t in r.get("threads_opened") or []:
            opened.setdefault(t, r["page"])
        for t in r.get("threads_closed") or []:
            closed.add(t)
    open_threads = [{"thread": t, "opened_on_page": p} for t, p in sorted(opened.items()) if t not in closed]

    # C2 — arcs: declared final state against the last logged state.
    declared, last = arcs(root, paths), {}
    for r in rows:
        for cid, value in (r.get("states") or {}).items():
            last[cid] = {"page": r["page"], "state": value}
    arc_rows = [{"id": cid, "name": a["name"], "declared_from": a["from"], "declared_to": a["to"],
                 "actual_final_state": last.get(cid, {}).get("state"),
                 "last_seen_page": last.get(cid, {}).get("page"),
                 "ever_appeared": cid in last}
                for cid, a in declared.items()]

    # C3 — chapter balance and the flag ratio.
    words = {r["page"]: r.get("words") for r in rows}
    chapter_rows = []
    for i, span in enumerate(derived["chapter_spans"], start=1):
        pages = [b["page"] for b in beats if b["chapter"] == i]
        counted = [words[p] for p in pages if words.get(p) is not None]
        chapter_rows.append({"chapter": i, "pages_written": len(pages),
                             "pages_derived": derived["chapter_sizes"][i - 1],
                             "matches_derivation": len(pages) == derived["chapter_sizes"][i - 1],
                             "words": sum(counted),
                             "pages_without_a_word_count": len(pages) - len(counted)})
    act_rows = []
    for span in derived["act_spans"]:
        declared_pages = [b["page"] for b in beats if b["act"] == span["act"]]
        act_rows.append({"act": span["act"], "derived_span": [span["first"], span["last"]],
                         "beat_sheet_pages": declared_pages,
                         "matches_derivation": declared_pages == list(range(span["first"], span["last"] + 1))})

    flagged = [{"page": r["page"], "reason": r.get("flag_reason")} for r in rows if r.get("flagged")]
    total = len({r["page"] for r in rows})
    ratio = len(flagged) / total if total else 0.0

    repairs = [{"page": r["page"], "supersedes": r["supersedes"], "reason": r.get("repair_reason")}
               for r in rows if r.get("supersedes") is not None]
    retries = {r["page"]: r.get("retries", 0) for r in rows}

    return {"open_threads": open_threads, "arcs": arc_rows, "chapters": chapter_rows, "acts": act_rows,
            "flagged_pages": flagged, "flag_ratio": round(ratio, 4),
            "max_flagged_ratio": config["control"]["max_flagged_ratio"],
            "flag_ratio_within_ceiling": ratio <= config["control"]["max_flagged_ratio"],
            "continuity_repairs": repairs, "max_continuity_repairs": config["control"]["max_continuity_repairs"],
            "retries_per_page": retries, "supersessions": derived["supersessions"],
            "derived_shape": {"chapter_sizes": derived["chapter_sizes"],
                              "act_spans": derived["act_spans"],
                              "anchor_pages": derived["anchor_pages"],
                              "word_band": derived["word_band"]}}


def manuscript(story_id, config=None, derived=None):
    """C4 — rebuilt from pages/, never edited in place (FR-29)."""
    config = config or load("config.json")
    derived = derived or derive(config, story_id)
    root, paths = derived["story_root"], config["paths"]
    beats = json.load(open(os.path.join(root, paths["beats"]), encoding="utf-8"))
    out, seen = [], None
    for beat in sorted(beats, key=lambda b: b["page"]):
        path = os.path.join(root, paths["pages_dir"], "%02d.md" % beat["page"])
        if not os.path.exists(path):
            continue
        body = read(path)
        if body.startswith("---"):
            body = body.split("---", 2)[-1].strip()
        if beat["chapter"] != seen:
            out.append("## %d. %s" % (beat["chapter"], beat["chapter_title"]))
            seen = beat["chapter"]
        out.append(body)
    text = "\n\n".join(out) + "\n"
    write_atomic(os.path.join(root, paths["manuscript"]), text)
    return text


if __name__ == "__main__":
    what, story = sys.argv[1], sys.argv[2]
    if what == "audit":
        print(json.dumps(audit(story), indent=2, ensure_ascii=False))
    elif what == "manuscript":
        print("%d characters written" % len(manuscript(story)))
