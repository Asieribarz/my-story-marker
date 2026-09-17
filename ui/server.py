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

    open_threads = []
    for record in deltas:
        for thread in record.get("threads_opened", []):
            open_threads.append(thread)
        for thread in record.get("threads_closed", []):
            if thread in open_threads:
                open_threads.remove(thread)

    # A chapter-close repair appends a second record for a page it corrects
    # (FR-39, `supersedes`). The later record is the one that stands.
    latest = {}
    for record in deltas:
        latest[record["page"]] = record

    beat_by_page = {beat["page"]: beat for beat in beats}
    pages = []
    for record in sorted(latest.values(), key=lambda r: r["page"]):
        beat = beat_by_page.get(record["page"], {})
        count = record.get("words", 0)
        pages.append({
            "page": record["page"],
            "chapter": record.get("chapter"),
            "chapter_title": beat.get("chapter_title"),
            "act": beat.get("act"),
            # The beat sheet the pages were written from is authoritative for
            # this story; the derived anchors describe the current config,
            # which may no longer be the one the story was written at.
            "anchor": beat.get("anchor", record["page"] in derived["anchor_pages"]),
            "words": count,
            "in_band": band["min"] <= count <= band["max"],
            "retries": record.get("retries", 0),
            "flagged": bool(record.get("flagged")),
            "summary": record.get("summary", ""),
        })

    return {
        "story_id": story_id,
        "derived": derived,
        "pages": pages,
        "totals": {
            "pages_total": config["organization"]["pages_total"],
            "pages_written": len(pages) or written,
            "page_files": written,
            "repairs": len(deltas) - len(pages),
            "beats_planned": len(beats),
            "digests": len(digests),
            "retries": sum(page["retries"] for page in pages),
            "flagged": sum(1 for page in pages if page["flagged"]),
            "out_of_band": sum(1 for page in pages if not page["in_band"]),
            "mean_words": round(sum(p["words"] for p in pages) / len(pages)) if pages else 0,
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
