"""Ablation: keyword only | vector only | hybrid | hybrid + reranker  ->  recall@k and latency.
Uses the same cross-encoder as the pipeline. Run from the project folder:  python eval/ablation.py"""
import json, sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from eval.retrieval_eval import load_eval, evaluate, KS

RERANKER, POOL = "cross-encoder/ms-marco-MiniLM-L-6-v2", 20

def main():
    from sentence_transformers import CrossEncoder
    from src.retrieve import retrieve
    rows, ce = load_eval(), CrossEncoder(RERANKER)
    def hybrid_rerank(q, k):
        cands = retrieve(q, POOL, "hybrid")
        scores = ce.predict([(q, c["text"]) for c in cands])
        return [cands[i] for i in sorted(range(len(cands)), key=lambda i: -scores[i])][:k]
    systems = {"Keyword only (BM25)": lambda q, k: retrieve(q, k, "bm25"), "Vector only": lambda q, k: retrieve(q, k, "vector"),
               "Hybrid (BM25 + vector)": lambda q, k: retrieve(q, k, "hybrid"), "Hybrid + reranker": hybrid_rerank}
    res = {name: evaluate(fn, rows) for name, fn in systems.items()}
    head = "| System | " + " | ".join(f"R@{k}" for k in KS) + " | ms/query |\n|---|" + "---|" * (len(KS) + 1)
    lines = [f"| {n} | " + " | ".join(f"{r[f'recall@{k}']:.2f}" for k in KS) + f" | {r['ms']:.0f} |" for n, r in res.items()]
    table = f"{head}\n" + "\n".join(lines) + f"\n\n{len(rows)} answerable questions."
    print(table)
    pathlib.Path("eval/results").mkdir(parents=True, exist_ok=True)
    pathlib.Path("eval/results/ablation.md").write_text(table, encoding="utf-8")
    json.dump({k: {a: b for a, b in v.items() if a != "misses"} for k, v in res.items()}, open("eval/results/ablation.json", "w"), indent=1)

if __name__ == "__main__":
    main()
