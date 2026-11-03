"""Chunk-size experiment. Re-chunks the raw pages at several sizes in data/exp/ (data/chunks.jsonl is NOT touched),
embeds each version and measures retrieval recall on the eval set. Needs data/raw/ (python -m src.scrape).
Run from the project folder:  python eval/chunk_experiment.py [--sizes 150,225,375,600] [--overlap 2] [--file data/eval.jsonl]
Sizes are in WORDS: 225 / 375 / 600 words are about 300 / 500 / 800 tokens. About 3 minutes per size.
Recall is page-level (is the gold page among the top-k chunks?), so it can be compared across chunk sizes."""
import json, pathlib, re, sys, time
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
KS = [1, 3, 5, 10]

def arg(name, default): return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default
def norm_url(u): return re.sub(r"\.html$", "", u.strip()).rstrip("/")

def load_eval():
    rows = [json.loads(l) for l in open(arg("--file", "data/eval.jsonl"), encoding="utf-8-sig") if l.strip()]
    return [r for r in rows if r.get("answerable", True) and r.get("source_url")]

def evaluate(search, rows):
    """search(question, k) -> list of chunks. Page-level recall@k and mean latency in ms."""
    kmax, hits, total = max(KS), {k: 0 for k in KS}, 0.0
    if rows: search(rows[0]["question"], kmax)   # warm-up: loading a model must not count as latency
    for r in rows:
        t = time.perf_counter(); res = search(r["question"], kmax); total += time.perf_counter() - t
        urls, gold = [norm_url(c["url"]) for c in res], norm_url(r["source_url"])
        for k in KS: hits[k] += gold in urls[:k]
    n = max(1, len(rows))
    return {**{f"recall@{k}": hits[k] / n for k in KS}, "ms": 1000 * total / n}

def main():
    from sentence_transformers import CrossEncoder
    from src import chunk as chunker
    from src.index import embed
    from src.retrieve import Retriever
    sizes = [int(s) for s in arg("--sizes", "150,225,375,600").split(",")]
    overlap = int(arg("--overlap", "2"))
    rows, ce = load_eval(), CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
    print("answerable eval questions:", len(rows))
    table, raw = [], {}
    for size in sizes:
        path = pathlib.Path("data/exp") / f"chunks_{size}.jsonl"
        n, _ = chunker.build(size, overlap, path)
        chunks = [json.loads(l) for l in open(path, encoding="utf-8")]
        avg = sum(len(c["text"].split()) for c in chunks) / max(1, len(chunks))
        print(f"\nsize {size} words: {n} chunks, avg {avg:.0f} words; embedding...")
        R = Retriever(chunks_path=path, embeddings=embed([c["text"] for c in chunks]))
        def rerank(q, k, R=R):
            cands = R.search(q, 20, "hybrid"); sc = ce.predict([(q, c["text"]) for c in cands])
            return [cands[i] for i in sorted(range(len(cands)), key=lambda i: -sc[i])][:k]
        res = {"BM25": evaluate(lambda q, k: R.search(q, k, "bm25"), rows), "Vector": evaluate(lambda q, k: R.search(q, k, "vector"), rows),
               "Hybrid": evaluate(lambda q, k: R.search(q, k, "hybrid"), rows), "Hybrid+rerank": evaluate(rerank, rows)}
        raw[size] = {"chunks": n, "avg_words": avg, **{k: v for k, v in res.items()}}
        table.append(f"| {size} (~{round(size / 0.75)} tok) | {n} | {avg:.0f} | " + " | ".join(f"{res[s]['recall@5']:.2f}" for s in res) + f" | {res['Hybrid+rerank']['recall@10']:.2f} |")
        print(table[-1])
    head = "| Chunk size (words) | Chunks | Avg words | BM25 R@5 | Vector R@5 | Hybrid R@5 | Hybrid+rerank R@5 | Hybrid+rerank R@10 |\n|---|---|---|---|---|---|---|---|"
    out = head + "\n" + "\n".join(table) + f"\n\n{len(rows)} answerable questions, page-level recall, overlap {overlap} sentences."
    print("\n" + out)
    pathlib.Path("eval/results").mkdir(parents=True, exist_ok=True)
    pathlib.Path("eval/results/chunk_size.md").write_text(out, encoding="utf-8")
    json.dump(raw, open("eval/results/chunk_size.json", "w"), indent=1)

if __name__ == "__main__":
    main()
