"""MAYA: recall@k over data/eval.jsonl. A hit = a retrieved chunk whose url == source_url (and text overlaps source_passage)."""
import json
from src.retrieve import retrieve

def recall_at_k(k=5, mode="hybrid"):
    rows = [json.loads(l) for l in open("data/eval.jsonl", encoding="utf-8")]
    rows = [r for r in rows if r["answerable"]]
    hits = sum(any(c["url"] == r["source_url"] for c in retrieve(r["question"], k, mode)) for r in rows)
    return hits / max(1, len(rows))

if __name__ == "__main__":
    for mode in ("bm25", "vector", "hybrid"):
        print(mode, "recall@5 =", round(recall_at_k(5, mode), 3))
