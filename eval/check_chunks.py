"""Sanity checks after chunking + indexing. Run from the project folder: python eval/check_chunks.py"""
import json, re, sys, pathlib, collections
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

rows = [json.loads(l) for l in open("data/chunks.jsonl", encoding="utf-8")]
body = lambda r: r["text"].split("\n", 1)[-1]
norm = lambda s: re.sub(r"\W+", " ", s.lower()).strip()
print("chunks:", len(rows))

c = collections.Counter(norm(body(r)) for r in rows)
print("duplicate bodies:", sum(v - 1 for v in c.values()))
kt = [r for r in rows if r["section"].strip().lower() == "key terms"]
print("'Key Terms' chunks:", len(kt), "| distinct bodies:", len({norm(body(r)) for r in kt}))

low = [r for r in rows if body(r)[:1].islower()]
print(f"chunks starting lowercase: {len(low)} ({100 * len(low) / len(rows):.1f}%)")
for r in low[:5]: print("   e.g.", repr(body(r)[:70]), "|", r["url"].split("/")[-1])

try:
    from src.retrieve import retrieve
    q = "What is the minimum contrast for normal text?"
    res = retrieve(q, 5)
    print("\nQuery:", q)
    for i, r in enumerate(res, 1):
        print(f"  {i}. {r['url'].split('/')[-1]:30} | {r['section'][:25]:25} | has 4.5:1: {'4.5:1' in r['text']}")
except Exception as e:
    print("\n(retrieval check skipped:", e, ")")
