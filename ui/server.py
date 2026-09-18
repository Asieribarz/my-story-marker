"""Local control panel for the story agent.

Serves a two-pane UI: configuration editing on one side, run progress on the
other. Standard library only, no build step, bound to localhost.

    python ui/server.py            # then open http://127.0.0.1:8765

The server reads and writes config.json at the repository root, and reads the
artefacts of each story workspace under paths.stories_root. It writes nothing
inside a story workspace.
"""

import json
import os
import re
import sys
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import derive as derivation

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(ROOT, "config.json")
STATIC = os.path.join(ROOT, "ui", "static")
HOST, PORT = "127.0.0.1", 8765

# Only these groups are editable from the UI. `paths` is deliberately absent:
# a path edited by hand is how a run escapes its workspace (FR-45, I-9).
EDITABLE = ("organization", "page", "story", "context", "bible", "control", "model")


def read_config():
    return derivation.load(CONFIG_PATH)


def story_ids(config):
    stories_root = os.path.join(ROOT, config["paths"]["stories_root"])
    if not os.path.isdir(stories_root):
        return []
    return sorted(
        name for name in os.listdir(stories_root)
        if os.path.isdir(os.path.join(stories_root, name))
    )


def read_jsonl(path):
    if not os.path.exists(path):
        return []
    records = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def thread_key(thread):
    """Sort t1, t2, t10 by their number rather than by their spelling."""
    digits = re.sub(r"\D", "", str(thread))
    return (int(digits) if digits else 0, str(thread))


def thread_lives(deltas, standing):
    """Every thread, with the page that opened it and the page that closed it.

    Replay prefers a superseding record (TR-04c), so a thread minted by a
    record that a later continuity repair replaced vanishes from the register
    along with the prose that opened it. Minting is monotonic, so the
    identifier never returns to the pool and the sequence is left with a hole
    that the log cannot account for on its own. Those are reported as retired
    rather than silently skipped: a gap nobody explains is indistinguishable
    from a thread that was genuinely lost.
    """
    opened, closed = {}, {}
    for record in standing:
        for thread in record.get("threads_opened", []):
            opened.setdefault(thread, record["page"])
        for thread in record.get("threads_closed", []):
            closed.setdefault(thread, record["page"])

    minted = set()
    for record in deltas:
        minted.update(record.get("threads_opened", []))

    lives = [
        {"id": thread, "opened": page, "closed": closed.get(thread)}
        for thread, page in sorted(opened.items(), key=lambda item: thread_key(item[0]))
    ]
    retired = sorted(minted - set(opened), key=thread_key)
    return lives, retired


def structural_roles(page, derived, anchor):
    """What this page is being asked to do at once.

    Each role is a demand the beat sheet places on one page: turning the story,
    closing a chapter, opening one, crossing an act boundary. They are computed
    from the derivation, never stored. Where several land together the page is
    carrying several jobs, and that is worth seeing next to where the retries
    fell.
    """
    roles = []
    if anchor:
        roles.append("anchor")
    for span in derived["chapter_spans"]:
        if page == span["last"]:
            roles.append("chapter close")
        if page == span["first"] and page != 1:
            roles.append("chapter open")
    for span in derived["act_spans"]:
        if page == span["first"] and page != 1:
            roles.append("act %s" % span["act"])
    return roles


def progress(config, story_id):
    """Everything the progress pane shows, read from the story's own artefacts."""
    derived = derivation.derive(config, story_id)
    root = os.path.join(ROOT, config["paths"]["stories_root"], story_id)
    paths = config["paths"]

    deltas = read_jsonl(os.path.join(root, paths["state_log"]))
    beats_path = os.path.join(root, paths["beats"])
    beats = []
    if os.path.exists(beats_path):
        with open(beats_path, encoding="utf-8") as handle:
            beats = json.load(handle)

    pages_dir = os.path.join(root, paths["pages_dir"])
    written = 0
    if os.path.isdir(pages_dir):
        written = len([name for name in os.listdir(pages_dir)
                        if re.fullmatch(r"\d+\.md", name)])

    digests_dir = os.path.join(root, paths["chapter_digests_dir"])
    digests = sorted(os.listdir(digests_dir)) if os.path.isdir(digests_dir) else []

    band = derived["word_band"]

    # A chapter-close repair appends a second record for a page it corrects
    # (FR-39, `supersedes`). The later record is the one that stands.
    latest = {}
    repairs_by_page = {}
    for record in deltas:
        if record["page"] in latest:
            repairs_by_page[record["page"]] = repairs_by_page.get(record["page"], 0) + 1
        latest[record["page"]] = record

    standing = sorted(latest.values(), key=lambda r: r["page"])
    lives, retired_threads = thread_lives(deltas, standing)
    open_threads = [life["id"] for life in lives if life["closed"] is None]

    beat_by_page = {beat["page"]: beat for beat in beats}
    pages = []
    for record in standing:
        beat = beat_by_page.get(record["page"], {})
        count = record.get("words", 0)
        anchor = beat.get("anchor", record["page"] in derived["anchor_pages"])
        pages.append({
            "page": record["page"],
            "chapter": record.get("chapter"),
            "chapter_title": beat.get("chapter_title"),
            "act": beat.get("act"),
            # The beat sheet the pages were written from is authoritative for
            # this story; the derived anchors describe the current config,
            # which may no longer be the one the story was written at.
            "anchor": anchor,
            "words": count,
            "in_band": band["min"] <= count <= band["max"],
            "over_target": count - band["target"],
            "retries": record.get("retries", 0),
            "repairs": repairs_by_page.get(record["page"], 0),
            "roles": structural_roles(record["page"], derived, anchor),
            "flagged": bool(record.get("flagged")),
            "summary": record.get("summary", ""),
        })

    control = config["control"]
    # A state record with no word count is not a page of zero words: it is a
    # page whose length was never logged. Averaging it in would report a mean
    # the run never wrote, so it is counted separately and named.
    counted = [p for p in pages if p["words"] > 0]
    mean = round(sum(p["words"] for p in counted) / len(counted)) if counted else 0
    repairs = len(deltas) - len(pages)

    return {
        "story_id": story_id,
        "derived": derived,
        "pages": pages,
        "threads": lives,
        "retired_threads": retired_threads,
        # Each budget is a ceiling from config.json against what this run spent.
        # A budget read only at the end is a budget nobody can act on.
        "budgets": [
            {"key": "retries", "spent": sum(p["retries"] for p in pages),
             "ceiling": control["max_retries_per_page"] * max(len(pages), 1),
             "unit": "attempts", "governs": "control.max_retries_per_page, per page"},
            {"key": "repairs", "spent": repairs,
             "ceiling": control["max_continuity_repairs"],
             "unit": "repairs", "governs": "control.max_continuity_repairs, per run"},
            {"key": "flagged", "spent": sum(1 for p in pages if p["flagged"]),
             "ceiling": round(control["max_flagged_ratio"] * max(len(pages), 1), 2),
             "unit": "pages", "governs": "control.max_flagged_ratio of pages written"},
        ],
        "totals": {
            "pages_total": config["organization"]["pages_total"],
            "pages_written": len(pages) or written,
            "page_files": written,
            "repairs": repairs,
            "beats_planned": len(beats),
            "digests": len(digests),
            "retries": sum(page["retries"] for page in pages),
            "flagged": sum(1 for page in pages if page["flagged"]),
            "out_of_band": sum(1 for page in pages if not page["in_band"]),
            "mean_words": mean,
            # What the run wrote against what it was asked for. Both measured
            # runs came in above target, and every length retry was a page over
            # the ceiling, so the direction of this number is the finding.
            "length_bias": round(mean / band["target"], 3) if counted and band["target"] else None,
            "over_target": sum(1 for p in counted if p["over_target"] > 0),
            "counted": len(counted),
            "uncounted": [p["page"] for p in pages if p["words"] <= 0],
            "open_threads": open_threads,
            "manuscript": os.path.exists(os.path.join(root, paths["manuscript"])),
            "report": os.path.exists(os.path.join(root, paths["report"])),
        },
    }


def manuscript(config, story_id):
    """The written novel: the assembled manuscript and each page's prose."""
    root = os.path.join(ROOT, config["paths"]["stories_root"], story_id)
    paths = config["paths"]

    manuscript_path = os.path.join(root, paths["manuscript"])
    text = ""
    if os.path.exists(manuscript_path):
        with open(manuscript_path, encoding="utf-8") as handle:
            text = handle.read()

    pages_dir = os.path.join(root, paths["pages_dir"])
    pages = []
    if os.path.isdir(pages_dir):
        for name in sorted(name for name in os.listdir(pages_dir)
                           if re.fullmatch(r"\d+\.md", name)):
            with open(os.path.join(pages_dir, name), encoding="utf-8") as handle:
                raw = handle.read()
            front, body = {}, raw
            if raw.startswith("---"):
                _, block, body = raw.split("---", 2)
                for line in block.strip().splitlines():
                    if ":" in line:
                        key, value = line.split(":", 1)
                        front[key.strip()] = value.strip()
            pages.append({
                "page": int(front.get("page", name[:-3])),
                "chapter": front.get("chapter"),
                "chapter_title": front.get("chapter_title"),
                "act": front.get("act"),
                "anchor": front.get("anchor") == "true",
                "words": int(front.get("words", 0) or 0),
                "flagged": front.get("flagged") == "true",
                "text": body.strip(),
            })

    return {"story_id": story_id, "manuscript": text, "pages": pages}


def apply_edits(config, edits):
    """Merge the submitted groups into the config, leaving `paths` untouched."""
    merged = json.loads(json.dumps(config))
    for group, values in edits.items():
        if group not in EDITABLE:
            raise derivation.ConfigError("group %r is not editable from the UI" % group)
        for key, value in values.items():
            if key not in merged[group]:
                raise derivation.ConfigError("unknown parameter %s.%s" % (group, key))
            merged[group][key] = value
    return merged


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=STATIC, **kwargs)

    def log_message(self, fmt, *args):
        sys.stderr.write("%s\n" % (fmt % args))

    def send_json(self, payload, status=200):
        body = json.dumps(payload, indent=1).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        route = urlparse(self.path)
        query = parse_qs(route.query)
        try:
            if route.path == "/api/config":
                config = read_config()
                story = (query.get("story") or [None])[0]
                derived = derivation.derive(config, story)
                self.send_json({
                    "config": config,
                    "derived": derived,
                    "editable": list(EDITABLE),
                    "problems": derivation.validate(config, derived),
                    "stories": story_ids(config),
                })
                return
            if route.path == "/api/progress":
                config = read_config()
                stories = story_ids(config)
                story = (query.get("story") or stories[:1] or [None])[0]
                if not story:
                    self.send_json({"error": "no story workspace found"}, 404)
                    return
                self.send_json(progress(config, story))
                return
            if route.path == "/api/manuscript":
                config = read_config()
                stories = story_ids(config)
                story = (query.get("story") or stories[:1] or [None])[0]
                if not story:
                    self.send_json({"error": "no story workspace found"}, 404)
                    return
                self.send_json(manuscript(config, story))
                return
        except Exception as error:  # surfaced in the UI rather than the console
            self.send_json({"error": "%s: %s" % (type(error).__name__, error)}, 500)
            return
        super().do_GET()

    def do_PUT(self):
        if urlparse(self.path).path != "/api/config":
            self.send_json({"error": "not found"}, 404)
            return
        length = int(self.headers.get("Content-Length", 0))
        try:
            edits = json.loads(self.rfile.read(length) or b"{}")
            candidate = apply_edits(read_config(), edits)
            derived = derivation.derive(candidate)
            problems = derivation.validate(candidate, derived)
            if problems:
                # abort_on_invalid_config: nothing is written until it is valid.
                self.send_json({"saved": False, "problems": problems, "derived": derived}, 400)
                return
            with open(CONFIG_PATH, "w", encoding="utf-8", newline="\n") as handle:
                json.dump(candidate, handle, indent=2, ensure_ascii=False)
                handle.write("\n")
            self.send_json({
                "saved": True,
                "config": candidate,
                "derived": derived,
                "problems": [],
            })
        except Exception as error:
            self.send_json(
                {"saved": False, "problems": ["%s: %s" % (type(error).__name__, error)]}, 400
            )


if __name__ == "__main__":
    print("Story agent control panel  ->  http://%s:%s" % (HOST, PORT))
    print("Editing %s" % CONFIG_PATH)
    HTTPServer((HOST, PORT), Handler).serve_forever()
