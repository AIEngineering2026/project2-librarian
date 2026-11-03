# Design: data, index and search (Mayssa's part)

Corpus: WCAG 2.2 (W3C). Users: developers who need to check accessibility rules. Draft of 3 Nov 2026. Items in [brackets] are for a teammate to confirm.

## 1. Corpus and users

| Source | Pages | Why |
|---|---|---|
| WCAG 2.2 specification | 1 (very long) | The normative rules |
| Understanding WCAG 2.2 | 120 | Intent, benefits and examples for each success criterion |
| Techniques for WCAG 2.2 | 436 | Concrete ways to meet or fail a criterion |

All pages are public W3C documents with no personal data. We scraped 557 pages (`src/scrape.py`: crawl two levels deep from each index page, cached on disk, 0.3 s between requests; one dead link returned 404 and was skipped). After merging URL variants of the same page (with and without `.html`), the corpus has **545 distinct pages**.

## 2. Chunking (`src/chunk.py`)

Each page is split at its h2 to h4 headings. Inside a section, whole sentences are packed into chunks of at most **375 words (about 500 tokens)**, and each new chunk repeats up to 2 sentences from the previous one (capped at a quarter of the chunk size). Chunks keep their page title, section heading and URL, which is what makes citations possible. Chunks with the same text are stored once.

How the chunker evolved (each step fixed a problem found by testing):

| Version | Chunks | Problem found |
|---|---|---|
| 1. Fixed word windows | 4,749 | Same page scraped under two URLs; chunks cut mid-sentence |
| 2. URL variants merged | 4,522 | 416 repeated chunks, mostly the "Key Terms" glossary copied on many pages, flooding the top results |
| 3. Sentence-aware packing and repeated-chunk removal | **4,065** | Mid-sentence starts fell from 13.6% to 5.0% (the rest are glossary entries that start with the term); repeated chunks 416 to 0 |

Chunk-size experiment (`eval/chunk_experiment.py`, 33 reviewed questions, page-level recall@5; the sentence packing and the headings keep chunks short, so the average size moves little):

| Max size (words) | Chunks | Avg words | BM25 | Vector | Hybrid | Hybrid + reranker |
|---|---|---|---|---|---|---|
| 150 | 5,378 | 104 | 1.00 | 0.82 | 0.97 | 0.94 |
| 225 | 4,596 | 121 | 0.94 | 0.82 | 0.94 | 0.94 |
| **375** | **4,065** | **137** | 0.91 | 0.82 | 0.97 | 0.94 |
| 600 | 3,835 | 144 | 0.91 | 0.82 | 0.94 | 0.94 |

Decision: keep 375 words. Hybrid recall is the same within one question (about 3 points) at every size, and 375 words needs 24% fewer chunks than 150 words. BM25 alone improves with smaller chunks, but this did not carry over to hybrid search. This experiment used a 33-question set and page-level recall, so it is a rough guide.

## 3. Index (`src/index.py`, `src/retrieve.py`)

- **Keyword index:** BM25 (`rank_bm25`), built in memory from `data/chunks.jsonl` in under a second at start-up.
- **Vector index:** one normalised embedding per chunk from `all-MiniLM-L6-v2` (384 dimensions), stored as a flat numpy file (`data/index/embeddings.npy`, 6.2 MB). Search is an exact cosine similarity (one matrix product).
- **Fusion:** reciprocal rank fusion (constant 60) over the top 30 results of each list.
- **Safety check:** `meta.json` stores a hash of the chunk ids, and `retrieve()` refuses to run if the index does not match `chunks.jsonl`.

Why a flat file instead of a vector database: the brief allows it, and at 4,065 chunks exact search takes milliseconds, so an approximate index would only add error. We first used Chroma, but it needs a newer SQLite than Streamlit Cloud provides, and the cloud has no persistent disk to build an index on. The committed file means a fresh clone or a cloud deployment needs no build step. Trade-off: memory and time grow linearly. At 100 times the corpus (about 400,000 chunks) the matrix would be about 0.6 GB, and a vector database or an approximate index would become worthwhile.

## 4. Retrieval and reranking

Pipeline for each question (details in README): optional rewrite into search queries, hybrid search, cross-encoder rerank (`ms-marco-MiniLM-L-6-v2`), then the answer model. With one search query, 20 candidates go to the reranker; with several queries, 10 per query are merged. The reranker keeps the top 5 chunks for the answer model, and the question is refused when the best rerank score is below `MIN_SCORE = 0` (a threshold sweep showed that raising it only adds false "I don't know" answers).

Ablation (`eval/ablation.py`, 110 reviewed questions, passage-level recall: a top-k chunk must contain the gold passage):

| System | R@1 | R@3 | R@5 | R@10 | MRR@10 | p50 search |
|---|---|---|---|---|---|---|
| BM25 only | 0.59 | 0.76 | 0.85 | 0.92 | 0.70 | 15 ms |
| Vector only | 0.48 | 0.69 | 0.73 | 0.81 | 0.59 | 10 ms |
| Hybrid (RRF) | 0.56 | 0.79 | 0.86 | 0.96 | 0.69 | 30 ms |
| Hybrid + reranker | **0.72** | **0.86** | **0.93** | 0.95 | **0.80** | about 0.8 to 2 s |

What it shows:
- **The reranker acts at the top of the list:** R@1 rises from 0.56 to 0.72 and MRR from 0.69 to 0.80. At k=5 it fixed 10 questions and broke 3 (exact sign test p of about 0.09, so suggestive rather than conclusive).
- **Hybrid's gain over BM25 is within noise** at R@1 to R@5 (95 vs 94 of 110 questions at R@5). It helps at R@10 (0.96 vs 0.92), so its role is to give the reranker a strong shortlist.
- **Vector search alone is clearly the weakest.**
- **The reranker is the latency cost:** about 0.8 s on one laptop and 2.0 s on another (search step only, models loaded). Week 8 savings should start here, for example by reranking fewer candidates (hybrid R@10 is already 0.96).

## 5. Evaluation set (`data/eval.jsonl`)

110 answerable and 12 unanswerable questions. The answerable ones were drafted by a language model from randomly chosen chunks (45% Understanding, 35% Techniques, 20% specification; at most one per page), and kept only if the quoted evidence really occurs in the chunk. Three team members then reviewed them and removed bad ones (document-structure questions, test-rule trivia, near-duplicates). The 12 unanswerable ones are off-topic and test "I don't know". For 17 gold passages that are repeated on more than 3 pages, only chunks from the source page count.

## 6. Known failure cases and limitations

Observed:
1. **Spec vs Understanding pages:** the specification page can outrank the Understanding page that answers a question (for example "What does Level AAA add for synchronized media?").
2. **Techniques crowd out Understanding pages** for general questions, because there are 436 Techniques pages and 120 Understanding pages.
3. **Off-topic questions still return results** ("capital of France" returned three unrelated technique pages), so refusing needs a score threshold on the reranker.
4. **The reranker broke 3 questions at k=5**: skipping repeated content, non-text content in electronic text, and activating an image link by script. [To check whether it returned another valid passage.]
5. **Repeated text is stored once:** a glossary entry shared by many pages is only retrievable from the first page that contained it.
6. **Tables, code blocks and cross-references** between success criteria are flattened to text.

Limitations of the evaluation:
- The questions were drafted from the passages, so they share words with their answers. This probably favours BM25 over vector search. Questions written by people are the check. We did not have time to add a hand-written subset, so the recall numbers for BM25 may be a little optimistic.
- With 110 questions, one question is 0.9 points and the 95% interval is about plus or minus 6 points, so small differences are not significant.
- Several questions can be answered from two pages (an Understanding page and a Technique page) but are scored against one.
- Latencies depend on the machine.
- The chunk-size experiment used the earlier 33-question set and page-level recall.

## 7. Reproduce

```
pip install -r requirements.txt
python eval/smoke_test.py      # checks the data, the index and a few canary searches
python eval/ablation.py        # the table in section 4
python -m src.scrape && python -m src.chunk && python -m src.index   # rebuild everything (about 10 minutes)
python eval/chunk_experiment.py --file data/eval.jsonl               # the table in section 2
```
