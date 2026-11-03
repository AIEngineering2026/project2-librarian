"""Smoke test for the data and search part. Run from the project folder:  python eval/smoke_test.py
Prints PASS/FAIL for every check and exits with code 1 if anything fails."""
import json, pathlib, re, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import numpy as np

fails = []
def check(name, ok, detail=""):
    print(("PASS  " if ok else "FAIL  ") + name + (f"   ({detail})" if detail else ""))
    if not ok: fails.append(name)

def main():
    from src.index import EMB, ids_hash
    from src.retrieve import retrieve
    rows = [json.loads(l) for l in open("data/chunks.jsonl", encoding="utf-8") if l.strip()]
    body = lambda r: r["text"].split("\n", 1)[-1]
    norm = lambda s: re.sub(r"\W+", " ", s.lower()).strip()
    check("chunks.jsonl has the agreed fields", all({"id", "text", "title", "section", "url"} <= set(r) for r in rows), f"{len(rows)} chunks")
    check("chunk ids are unique", len({r["id"] for r in rows}) == len(rows))
    bodies = [norm(body(r)) for r in rows]
    check("no repeated chunk text", len(set(bodies)) == len(bodies), f"{len(bodies) - len(set(bodies))} repeated")
    check("no .html or trailing-slash URL variants", not any(r["url"].endswith((".html", "/")) for r in rows))
    pages = {r["url"] for r in rows}
    check("corpus covers at least 400 pages", len(pages) >= 400, f"{len(pages)} pages")
    low = sum(body(r)[:1].islower() for r in rows) / max(1, len(rows))
    check("few chunks start mid-sentence (under 10%)", low < 0.10, f"{100 * low:.1f}%")
    longest = max(len(r["text"].split()) for r in rows)
    check("no oversized chunk (600 words or less)", longest <= 600, f"longest {longest} words")

    meta = json.load(open("data/index/meta.json"))
    emb = np.load("data/index/embeddings.npy")
    check("index matches chunks.jsonl", meta["ids_sha1"] == ids_hash(rows) and meta["n"] == len(rows) and meta["model"] == EMB)
    check("one unit-length vector per chunk", emb.shape[0] == len(rows) and abs(float(np.linalg.norm(emb[0])) - 1) < 1e-3, f"shape {emb.shape}")

    for mode in ("bm25", "vector", "hybrid"):
        res = retrieve("minimum contrast ratio", 5, mode)
        check(f"retrieve() works in {mode} mode", len(res) == 5 and all({"id", "text", "url", "score"} <= set(c) for c in res))
    for q, page in [("minimum contrast ratio", "contrast-minimum"), ("target size minimum", "target-size-minimum"),
                    ("keyboard trap", "no-keyboard-trap"), ("focus visible", "focus-visible")]:
        urls = [c["url"] for c in retrieve(q, 5, "hybrid")]
        check(f"'{q}' finds .../{page} in the top 5", any(u.endswith("/" + page) for u in urls))

    print("\nALL CHECKS PASSED" if not fails else f"\n{len(fails)} CHECK(S) FAILED: " + ", ".join(fails))
    sys.exit(1 if fails else 0)

if __name__ == "__main__":
    main()
