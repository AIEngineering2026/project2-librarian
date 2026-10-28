"""KHADIJA: re-score the saved hard-set answers of every OpenAI run with the CURRENT checks in experiment.py.
Same rule for every run, no new LLM calls (free, instant).   Run:  py -m eval.rescore
"""
import glob
import json

from eval.experiment import HARD, passes

TESTS = {t["q"]: t for t in HARD}

print(f"{'run':32} {'before':>7} {'after':>7}  still failing")
for path in sorted(glob.glob("eval/results/oa-*.json")):
    data = json.load(open(path, encoding="utf-8"))
    checks = data["quality"]
    after = [passes(TESTS[c["question"]], {"answer": c["answer"]}) for c in checks]
    label = data["summary"]["label"]
    failing = [c["question"][:28] for c, ok in zip(checks, after) if not ok]
    print(f"{label:32} {data['summary']['accuracy_hard']:>7} {sum(after):>4}/{len(after)}  {'; '.join(failing)}")