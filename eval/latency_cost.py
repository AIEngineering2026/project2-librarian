"""KHADIJA: measure latency (p50 / p95) and cost per request of the full pipeline.

Run from the project root:   py -m eval.latency_cost
Uses the questions in data/eval.jsonl if it exists (first 20), otherwise a built-in list.
Saves the numbers to eval/latency_cost_results.json and prints a table to paste in the report.
"""
import json
import time
from pathlib import Path

from src.pipeline import MODEL, answer

# Groq list prices in US$ per 1 million tokens -- CHECK https://groq.com/pricing and update if needed.
PRICE_INPUT_PER_M = 0.15            # answer model (gpt-oss-120b)
PRICE_OUTPUT_PER_M = 0.75
REWRITE_PRICE_INPUT_PER_M = 0.075   # rewrite model (gpt-oss-20b)
REWRITE_PRICE_OUTPUT_PER_M = 0.30

# Cost model assumption: how many questions per day today, and at 100x.
REQUESTS_PER_DAY_TODAY = 50

N_QUESTIONS = 20
FALLBACK_QUESTIONS = [
    "What is the minimum contrast for normal text?",
    "What is the minimum target size in WCAG 2.2?",
    "Does an icon-only button need a label?",
    "Do form inputs need visible labels?",
    "What contrast do user interface components need?",
    "Can content flash more than three times per second?",
    "Do videos need captions?",
    "Must all functionality be available from a keyboard?",
    "What is a focus indicator and when must it be visible?",
    "Do pages need a title?",
    "What does reflow mean in WCAG?",
    "Is dragging allowed without an alternative?",
    "What is the purpose of the lang attribute?",
    "How long should users have to read content with a time limit?",
    "What is consistent help in WCAG 2.2?",
    "What is the best pizza in Tunis?",
    "How do I build a Kubernetes cluster?",
    "Do images need alternative text?",
    "What is redundant entry?",
    "Should error messages describe how to fix the error?",
]


def load_questions():
    """Questions from Maya's data/eval.jsonl first, topped up with the built-in list to reach N."""
    qs = []
    path = Path("data/eval.jsonl")
    if path.exists():
        qs = [json.loads(line)["question"] for line in path.open(encoding="utf-8") if line.strip()]
    for q in FALLBACK_QUESTIONS:
        if len(qs) >= N_QUESTIONS:
            break
        if q not in qs:
            qs.append(q)
    return qs[:N_QUESTIONS]


def percentile(values, p):
    s = sorted(values)
    k = (len(s) - 1) * p / 100
    lo, hi = int(k), min(int(k) + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def main():
    questions = load_questions()
    print(f"Warming up (loading models)...")
    answer("warm up question about contrast")  # first call loads models; not counted

    rows = []
    for i, q in enumerate(questions, start=1):
        start = time.perf_counter()
        r = answer(q)
        seconds = time.perf_counter() - start
        u = r.get("usage", {})
        u = {k: u.get(k, 0) for k in ("prompt", "completion", "rewrite_prompt", "rewrite_completion")}
        cost = (u["prompt"] / 1e6 * PRICE_INPUT_PER_M + u["completion"] / 1e6 * PRICE_OUTPUT_PER_M
                + u["rewrite_prompt"] / 1e6 * REWRITE_PRICE_INPUT_PER_M
                + u["rewrite_completion"] / 1e6 * REWRITE_PRICE_OUTPUT_PER_M)
        rows.append({"question": q, "seconds": round(seconds, 3), "idk": r["answer"] == "I don't know.",
                     "prompt_tokens": u["prompt"], "completion_tokens": u["completion"], "cost_usd": cost})
        print(f"{i:2d}. {seconds:5.2f}s  {u['prompt']:5d} in / {u['completion']:4d} out  "
              f"{'IDK ' if rows[-1]['idk'] else '    '}{q[:60]}")
        time.sleep(1)  # stay under the free-tier rate limit

    secs = [r["seconds"] for r in rows]
    avg_cost = sum(r["cost_usd"] for r in rows) / len(rows)
    summary = {
        "model": MODEL,
        "n_requests": len(rows),
        "p50_seconds": round(percentile(secs, 50), 2),
        "p95_seconds": round(percentile(secs, 95), 2),
        "avg_prompt_tokens": round(sum(r["prompt_tokens"] for r in rows) / len(rows)),
        "avg_completion_tokens": round(sum(r["completion_tokens"] for r in rows) / len(rows)),
        "idk_count": sum(r["idk"] for r in rows),
        "cost_per_request_usd": round(avg_cost, 6),
        "cost_per_1000_requests_usd": round(avg_cost * 1000, 3),
        "monthly_cost_today_usd": round(avg_cost * REQUESTS_PER_DAY_TODAY * 30, 2),
        "monthly_cost_at_100x_usd": round(avg_cost * REQUESTS_PER_DAY_TODAY * 100 * 30, 2),
        "prices_per_million": {"answer_in": PRICE_INPUT_PER_M, "answer_out": PRICE_OUTPUT_PER_M,
                               "rewrite_in": REWRITE_PRICE_INPUT_PER_M, "rewrite_out": REWRITE_PRICE_OUTPUT_PER_M},
    }

    out = Path("eval/latency_cost_results.json")
    out.write_text(json.dumps({"summary": summary, "requests": rows}, indent=2), encoding="utf-8")

    print("\n| Metric | Value |\n|---|---|")
    for k, v in summary.items():
        print(f"| {k} | {v} |")
    print(f"\nSaved to {out}")


if __name__ == "__main__":
    main()