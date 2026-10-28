"""KHADIJA: Week 8 experiment runner.

One command = one experiment. It measures, with the SAME questions every time:
  - speed  : p50 / p95 end-to-end latency + average time per step   (20 latency questions)
  - cost   : average $ per request                                   (same 20 questions)
  - quality: automatic pass/fail on the 15 hard questions            (accuracy proxy until
             Maya's 100+ question eval is ready)
Results go to eval/results/<label>.json and one row is added to eval/results/experiments.md.

Examples (from the project root):
  py -m eval.experiment --label baseline
  py -m eval.experiment --label E1-rewrite-low --rewrite-effort low
  py -m eval.experiment --label E3-top3 --rewrite-effort low --top-k 3
"""
import argparse
import json
import re
import time
from pathlib import Path

import src.pipeline as pipeline
from eval.latency_cost import cost_usd, load_questions, percentile

RESULTS = Path("eval/results")

# Hard questions with automatic checks: every regex in "must" has to match the answer.
# "idk": True means the correct behaviour is to say "I don't know".
HARD = [
    {"q": "My grey text on a white background looks faint, is that a problem?", "must": [r"4\.5:1"]},
    {"q": "buttons too small?", "must": [r"\b24\b"]},
    {"q": "What contrast do large text and icons need?", "must": [r"large", r"icon", r"3:1"],
     "forbid": [r"large[^.\n]*?4\.5:1(?![^.\n]*aaa)"]},  # 4.5:1 for large text is the AAA value
    {"q": "What's the difference between 1.4.3 and 1.4.6?", "must": [r"4\.5:1", r"7:1"]},
    {"q": "Does disabled button text need good contrast?", "must": [r"\bno\b|exempt|not required"]},
    {"q": "Does a logo need to meet contrast rules?", "must": [r"exempt|no contrast requirement|\bno\b"],
     "forbid": [r"^yes"]},
    {"q": "Which success criteria are new in WCAG 2.2?", "must": [r"2\.4\.11", r"2\.5\.8", r"3\.3\.8"]},
    {"q": "Is 4.1.1 Parsing still required?", "must": [r"removed|obsolete"]},
    {"q": "At what width must content reflow without horizontal scrolling?", "must": [r"\b320\b"]},
    {"q": "How many times per second can content flash?", "must": [r"three|\b3\b"]},
    {"q": "Can I use a puzzle CAPTCHA on my login page?",
     "must": [r"3\.3\.8|accessible authentication|cognitive function"]},
    {"q": "What contrast does WCAG 3.0 require?", "idk": True},
    {"q": "Is WCAG legally required in Tunisia?", "idk": True},
    {"q": "minimun constrast for txt", "must": [r"4\.5:1"]},
    {"q": "Quel est le contraste minimum pour le texte ?", "must": [r"4\.5:1"]},
]


def normalise(text):
    """Make numbers comparable: '4,5 : 1' / '4.5 to 1' -> '4.5:1', '24 × 24' -> '24x24'."""
    t = text.lower().replace(",", ".").replace("×", "x").replace(" ", " ").replace(" ", " ")
    t = re.sub(r"\s*:\s*", ":", t)
    t = re.sub(r"(\d)\s+to\s+1\b", r"\1:1", t)
    return t


def passes(test, result):
    is_idk = result["answer"] == pipeline.IDK
    if test.get("idk"):
        return is_idk
    if is_idk:
        return False
    text = normalise(result["answer"])
    ok = all(re.search(p, text) for p in test.get("must", []))
    bad = any(re.search(p, text) for p in test.get("forbid", []))
    return ok and not bad


def cost_of(usage):
    return cost_usd(usage)


def run_one(question):
    start = time.perf_counter()
    r = pipeline.answer(question)
    return r, time.perf_counter() - start


def main():
    ap = argparse.ArgumentParser(description="Run one Week 8 experiment")
    ap.add_argument("--label", required=True, help="name of this experiment, e.g. E1-rewrite-low")
    ap.add_argument("--rewrite-effort", choices=["minimal", "low", "medium", "high"])
    ap.add_argument("--answer-effort", choices=["minimal", "low", "medium", "high"])
    ap.add_argument("--top-k", type=int, default=pipeline.TOP_K)
    ap.add_argument("--min-score", type=float, default=pipeline.MIN_SCORE)
    ap.add_argument("--skip-rewrite-if-clear", action="store_true")
    ap.add_argument("--cache", action="store_true")
    args = ap.parse_args()

    # apply the settings for this experiment
    pipeline.REWRITE_EFFORT = args.rewrite_effort
    pipeline.ANSWER_EFFORT = args.answer_effort
    pipeline.TOP_K = args.top_k
    pipeline.MIN_SCORE = args.min_score
    pipeline.SKIP_REWRITE_IF_CLEAR = args.skip_rewrite_if_clear
    pipeline.USE_CACHE = args.cache
    settings = {"provider": pipeline.PROVIDER, "answer_model": pipeline.MODEL,
                "rewrite_model": pipeline.REWRITE_MODEL,
                **{k: v for k, v in vars(args).items() if k != "label"}}
    print(f"Experiment '{args.label}' with {settings}")

    pipeline.answer("warm up question about contrast")  # load models, not counted
    pipeline._cache.clear()

    # ---- speed + cost on the 20 latency questions ----
    rows = []
    for i, q in enumerate(load_questions(), start=1):
        r, secs = run_one(q)
        rows.append({"question": q, "seconds": secs, "cost": cost_of(r.get("usage", {})),
                     "timings": r.get("timings", {}), "idk": r["answer"] == pipeline.IDK})
        print(f"  speed {i:2d}/20  {secs:5.2f}s  {q[:60]}")
        time.sleep(1)  # free-tier rate limit

    # ---- quality on the 15 hard questions ----
    checks = []
    for i, t in enumerate(HARD, start=1):
        r, secs = run_one(t["q"])
        ok = passes(t, r)
        checks.append({"question": t["q"], "pass": ok, "answer": r["answer"],
                       "searched": r.get("rewrite", {}).get("queries")})
        print(f"  quality {i:2d}/15  {'PASS' if ok else 'FAIL'}  {t['q'][:60]}")
        time.sleep(1)

    # ---- cache check: ask the 20 questions again ----
    repeat_p50 = None
    if args.cache:
        repeat = [run_one(row["question"])[1] for row in rows]
        repeat_p50 = round(percentile(repeat, 50), 3)

    secs = [r["seconds"] for r in rows]
    steps = {s: round(sum(r["timings"].get(s, 0) for r in rows) / len(rows), 2)
             for s in ("rewrite", "search", "rerank", "answer")}
    summary = {
        "label": args.label,
        "settings": settings,
        "p50_s": round(percentile(secs, 50), 2),
        "p95_s": round(percentile(secs, 95), 2),
        "avg_step_s": steps,
        "cost_per_request_usd": round(sum(r["cost"] for r in rows) / len(rows), 6),
        "accuracy_hard": f"{sum(c['pass'] for c in checks)}/{len(checks)}",
        "accuracy_hard_pct": round(100 * sum(c["pass"] for c in checks) / len(checks), 1),
        "failed": [c["question"] for c in checks if not c["pass"]],
        "repeat_p50_s_with_cache": repeat_p50,
    }

    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / f"{args.label}.json").write_text(
        json.dumps({"summary": summary, "speed": rows, "quality": checks}, indent=2, ensure_ascii=False),
        encoding="utf-8")

    table = RESULTS / "experiments.md"
    if not table.exists():
        table.write_text("| Experiment | p50 (s) | p95 (s) | rewrite / search / rerank / answer (s) "
                         "| Cost / request ($) | Hard-set accuracy |\n|---|---|---|---|---|---|\n",
                         encoding="utf-8")
    with table.open("a", encoding="utf-8") as f:
        f.write(f"| {args.label} | {summary['p50_s']} | {summary['p95_s']} | "
                f"{steps['rewrite']} / {steps['search']} / {steps['rerank']} / {steps['answer']} | "
                f"{summary['cost_per_request_usd']} | {summary['accuracy_hard']} |\n")

    print("\n" + json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"\nSaved eval/results/{args.label}.json and added a row to eval/results/experiments.md")


if __name__ == "__main__":
    main()