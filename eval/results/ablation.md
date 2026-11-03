| System | R@1 | R@3 | R@5 | R@10 | MRR@10 | URL-only R@5 | p50 ms | p95 ms |
|---|---|---|---|---|---|---|---|---|
| BM25 only | 0.59 | 0.76 | 0.85 | 0.92 | 0.70 | 0.89 | 15 | 24 |
| Vector only | 0.48 | 0.69 | 0.73 | 0.81 | 0.59 | 0.79 | 10 | 14 |
| Hybrid (BM25 + vector, RRF) | 0.56 | 0.79 | 0.86 | 0.96 | 0.69 | 0.91 | 30 | 47 |
| Hybrid + reranker | 0.72 | 0.86 | 0.93 | 0.95 | 0.80 | 0.90 | 2014 | 3092 |

110 answerable questions. R@k = a top-k chunk contains the gold passage (substring, a run of >= 60% of its words, or >= 85% of its words in order; for the 17 boilerplate passages found on > 3 pages, only chunks from the source page count). URL-only R@5 = the gold page is in the top 5 (inflated: the whole WCAG 2.2 spec is one URL). 110/110 gold passages are in data/chunks.jsonl at all. Latency = the search step only, models already loaded.
