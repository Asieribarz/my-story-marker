"""A7 — commit the staged bible to the bible, in one operation (FR-34, TR-24).

Performed by the orchestrator. No agent writes into the bible (FR-49).
"""
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ui.derive import load, derive

story = sys.argv[1]
cfg = load("config.json")
der = derive(cfg, story)
root, paths = der["story_root"], cfg["paths"]
staging = os.path.join(root, paths["staging_dir"])

real = os.path.realpath(root)
moves = [("premise.md", paths["premise"]), ("rules.md", paths["world_rules"]),
         ("beats.json", paths["beats"]), ("characters", paths["characters_dir"]),
         ("settings", paths["settings_dir"])]

for src, dest in moves:
    target = os.path.join(root, dest)
    # I-9 / FR-45: nothing may land outside the workspace.
    if not os.path.realpath(target).startswith(real):
        sys.exit("I-9 refused: %s resolves outside %s" % (target, real))

for src, dest in moves:
    s, t = os.path.join(staging, src), os.path.join(root, dest)
    if os.path.isdir(s):
        os.makedirs(t, exist_ok=True)
        for name in sorted(os.listdir(s)):
            shutil.copy2(os.path.join(s, name), os.path.join(t, name))
        print("committed %d files to %s" % (len(os.listdir(s)), dest))
    else:
        os.makedirs(os.path.dirname(t), exist_ok=True)
        shutil.copy2(s, t)
        print("committed %s" % dest)

shutil.rmtree(staging)
print("staging discarded")
