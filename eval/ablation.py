"""MAYA - T2. Ablation: which part of the search helps?  recall@k + search latency for
    BM25 only | vector only | hybrid | hybrid + reranker | (optional) hybrid + reranker + question rewriting

Scoring is the same as eval/retrieval_eval.py (a hit = a retrieved chunk contains the gold passage).
The reranker row uses the pipeline's own rerank() with the ORIGINAL question only (no rewriting), so it
is a fair comparison with the rows above it:
    cands = retrieve(q, k=20, mode="hybrid");  top = rerank([q], cands, top_k=10)

Run from the project root:
    py -m eval.ablation                 # 4 rows, no LLM calls, no Groq tokens used
    py -m eval.ablation --with-rewrite  # + 5th row = the full pipeline's search (1 gpt-oss-20b call per question)
Writes eval/results/ablation.md (table for the report) and eval/results/ablation.json
"""
import argparse
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from eval.retrieval_eval import KS, RESULTS, evaluate, prepare, save  # noqa: E402

POOL = 20   # candidates given to the reranker (same as pipeline.CANDIDATES)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--with-rewrite", action="store_true",
                    help="add the full-pipeline search row (calls the rewrite LLM once per question)")
    args = ap.parse_args()

    # src.pipeline creates a Groq client on import. The 4 basic rows never call Groq, so a missing key
    # must not stop them: load .env first, then put a placeholder only if there is still no key.
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    if not args.with_rewrite:
        os.environ.setdefault("GROQ_API_KEY", "not-needed-for-retrieval-only")
    import src.pipeline as p
    from src.retrieve import retrieve

    rows, gold = prepare()
    retrieve("warm up", k=1)                 # load the index + embedding model (not timed)
    p.get_reranker().predict([("warm up", "warm up")])

    def hybrid_rerank(q, k):
        cands = retrieve(q, k=POOL, mode="hybrid")
        return p.rerank([q], cands, top_k=k)

    systems = {
        "BM25 only": lambda q, k: retrieve(q, k, "bm25"),
        "Vector only": lambda q, k: retrieve(q, k, "vector"),
        "Hybrid (BM25 + vector, RRF)": lambda q, k: retrieve(q, k, "hybrid"),
        "Hybrid + reranker": hybrid_rerank,
    }

    if args.with_rewrite:
        def full_search(q, k):
            """Steps 1-3 of pipeline.answer(): rewrite -> search every query -> rerank. No answer call."""
            for attempt in range(5):
                try:
                    _, question_en, queries, _ = p.rewrite(q)
                    break
                except Exception as e:          # rewrite() already falls back on most errors
                    print(f"  rewrite error ({e}); retrying in {2 ** attempt * 5}s")
                    time.sleep(2 ** attempt * 5)
            searches = list(dict.fromkeys([q, *queries]))
            cands = p.gather_candidates(searches)
            time.sleep(1)                       # stay under the free-tier rate limit
            return p.rerank(list(dict.fromkeys([question_en, *queries])), cands, top_k=k)
        systems["Hybrid + reranker + rewriting (full pipeline)"] = full_search

    res = {}
    for name, fn in systems.items():
        print(f"running: {name}", flush=True)
        res[name] = evaluate(fn, rows, gold, label=name)
        r = res[name]
        print("   " + "  ".join(f"R@{k}={r[f'recall@{k}']:.3f}" for k in KS) + f"  p50={r['ms_p50']:.0f} ms")

    note = ("" if not args.with_rewrite else
            " The full-pipeline row's latency includes the rewrite LLM call and a 1 s pause per question.")
    md = save("ablation", res, rows, gold, extra_note=note)
    print("\n" + md + "\n\nSaved eval/results/ablation.md and eval/results/ablation.json")

    # questions the reranker fixed / broke compared with plain hybrid (useful for the failure-case section)
    h = {q["question"]: q["rank"] for q in res["Hybrid (BM25 + vector, RRF)"]["per_question"]}
    rr = {q["question"]: q["rank"] for q in res["Hybrid + reranker"]["per_question"]}
    ok = lambda x: x is not None and x <= 5
    fixed = [q for q in h if not ok(h[q]) and ok(rr[q])]
    broke = [q for q in h if ok(h[q]) and not ok(rr[q])]
    print(f"\nReranker fixed {len(fixed)} and broke {len(broke)} questions at k=5 (vs hybrid).")
    for q in broke[:10]:
        print("  broke:", q[:90])


if __name__ == "__main__":
    sys.stdout.reconfigure(errors="replace")
    main()
