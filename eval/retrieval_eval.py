"""Retrieval eval: recall@k per search mode on data/eval.jsonl (answerable rows only).
A hit = the gold page (source_url) is among the top-k retrieved chunks' pages. Page-level on purpose, so the score
stays comparable when we change chunk size. Run from the project folder:  python eval/retrieval_eval.py [--file data/eval.jsonl]"""
import json, re, sys, time, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
KS = [1, 3, 5, 10]

def norm_url(u): return re.sub(r"\.html$", "", u.strip()).rstrip("/")

def load_eval(path=None):
    path = path or (sys.argv[sys.argv.index("--file") + 1] if "--file" in sys.argv else "data/eval.jsonl")
    rows = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
    return [r for r in rows if r.get("answerable", True) and r.get("source_url")]

def evaluate(search, rows, ks=KS):
    """search(question, k) -> list of chunk dicts. Returns recall@k, mean latency (ms) and the missed rows."""
    kmax, hits, total, misses = max(ks), {k: 0 for k in ks}, 0.0, []
    if rows: search(rows[0]["question"], kmax)   # warm-up: loading the model must not count as latency
    for r in rows:
        t = time.perf_counter(); res = search(r["question"], kmax); total += time.perf_counter() - t
        urls, gold = [norm_url(c["url"]) for c in res], norm_url(r["source_url"])
        for k in ks: hits[k] += gold in urls[:k]
        if gold not in urls[:5]: misses.append({"question": r["question"], "gold": gold, "got": urls[:3]})
    n = max(1, len(rows))
    return {"n": len(rows), **{f"recall@{k}": hits[k] / n for k in ks}, "ms": 1000 * total / n, "misses": misses}

def main():
    from src.retrieve import retrieve
    rows = load_eval()
    print("answerable eval questions:", len(rows))
    out = {}
    for mode in ("bm25", "vector", "hybrid"):
        out[mode] = evaluate(lambda q, k, m=mode: retrieve(q, k, m), rows)
        print(f"{mode:8}", {k: round(v, 3) for k, v in out[mode].items() if k.startswith("recall")}, f"{out[mode]['ms']:.0f} ms")
    print("\nHybrid misses (first 10):")
    for m in out["hybrid"]["misses"][:10]: print(" -", m["question"][:80], "| gold:", m["gold"].split("/")[-1], "| got:", [u.split("/")[-1] for u in m["got"]])
    pathlib.Path("eval/results").mkdir(parents=True, exist_ok=True)
    json.dump(out, open("eval/results/retrieval.json", "w"), indent=1)

if __name__ == "__main__":
    main()
