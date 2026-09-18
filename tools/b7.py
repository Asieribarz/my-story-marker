"""B7 — write the page file, then append the state record. Code; the four
judgement fields arrive from the orchestrator-owned extraction call."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ui.derive import load, derive
from state import write_page, append_record
from validate import count_words

story, page, prose_path, extract_path = sys.argv[1], int(sys.argv[2]), sys.argv[3], sys.argv[4]
retries = int(sys.argv[5]) if len(sys.argv) > 5 else 0
flagged = "--flagged" in sys.argv
reasons = [a.split("=",1)[1] for a in sys.argv if a.startswith("--reason=")]
supersedes = next((int(a.split("=",1)[1]) for a in sys.argv if a.startswith("--supersedes=")), None)
repair = next((a.split("=",1)[1] for a in sys.argv if a.startswith("--repair=")), None)

cfg = load("config.json"); der = derive(cfg, story)
root, paths = der["story_root"], cfg["paths"]
beats = json.load(open(os.path.join(root, paths["beats"]), encoding="utf-8"))
beat = next(b for b in beats if b["page"] == page)
prose = open(prose_path, encoding="utf-8").read().strip()
ex = json.load(open(extract_path, encoding="utf-8"))

write_page(root, paths, page, beat, prose, flagged, reasons)
record = {"page": page, "chapter": beat["chapter"], "words": count_words(prose),
          "retries": retries, "flagged": flagged,
          "summary": ex["summary"], "states": ex.get("states") or {},
          "threads_opened": ex.get("threads_opened") or [],
          "threads_closed": ex.get("threads_closed") or [],
          "facts": ex.get("facts") or [], "supersedes": supersedes}
if flagged: record["flag_reason"] = "; ".join(reasons)
if repair: record["repair_reason"] = repair
append_record(root, paths, record)
print("page %02d written, %d words, %d facts, threads +%s -%s"
      % (page, record["words"], len(record["facts"]),
         record["threads_opened"], record["threads_closed"]))
