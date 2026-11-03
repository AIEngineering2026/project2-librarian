# Design: The Librarian (WCAG 2.2 RAG assistant)

Corpus: WCAG 2.2 (W3C). Users: developers who need to check accessibility rules. Draft of 3 Nov 2026. Items in [brackets] are for a teammate to confirm.

Sections 1 to 5 and 8 (data, index, search, eval set): Mayssa. Sections 6 and 7 (pipeline, generation evaluation): Maya, with Khadija's pipeline. Section 8 also lists the failures seen in the answers.

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

Why a flat file instead of a vector database: the brief allows it, and at 4,065 chunks exact search takes milliseconds, so an approximate index would only add error. We first used Chroma, but on Streamlit Cloud it needed a SQLite workaround (pysqlite3-binary), and because the cloud has no persistent disk the app rebuilt the index at every start (1 to 2 minutes). The committed file means a fresh clone or a cloud deployment needs no build step. Trade-off: memory and time grow linearly. At 100 times the corpus (about 400,000 chunks) the matrix would be about 0.6 GB, and a vector database or an approximate index would become worthwhile.

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

## 6. Pipeline and generation

```
question → rewrite (gpt-5-nano) → off-topic? → hybrid search (original + rewritten queries)
         → rerank (best 5) → best score < MIN_SCORE? → answer with citations (gpt-6-luna) → citation guard
```

- **Rewrite:** a small model turns the question into clear English plus 1 to 3 WCAG search queries (vague wording, typos, French). The original question is always searched too, so a bad rewrite cannot remove good results. Off-topic questions are flagged here and refused at once, with no search and no answer call.
- **Answer:** gpt-6-luna gets the 5 chunks numbered [1] to [5], must end every sentence with its source, report exceptions and name the conformance level. Uncited sentences are removed by a citation guard, and [n] is mapped back to the chunk id.
- **"I don't know" has three layers:** the off-topic flag in the rewrite, the reranker threshold (`MIN_SCORE = 0`), and the model's own refusal.
- **Week 8 setting (E8):** gpt-6-luna and gpt-5-nano with "low" reasoning effort. Reasoning tokens are billed as output, so this is where the cost was.

## 7. Generation evaluation (`eval/generation_eval.py`)

**Method.** Two phases: `answer()` runs once per question and everything is saved (answer, the 5 chunks, citations, tokens, time); an LLM judge then scores the saved file, so a judge problem never costs the answers again. Both phases resume after a rate limit or a crash. The answer is split into claims (sentences or list items, each with its [n]); the judge sees the question, the gold answer, the claims and the text of the cited chunks.

**Metrics.**
- **Accuracy** (headline): answerable questions judged "correct" plus off-topic questions answered "I don't know", over all questions. "Partial" counts 0 (a second figure counts it 0.5).
- **Faithfulness:** share of factual claims supported by the chunks they cite. A factual claim with no citation counts as unsupported.
- **Citation accuracy:** for each [n], does chunk n say what the sentence claims?
- **"I don't know" accuracy:** refuse the 12 off-topic questions and only those.

**Judge.** gpt-4.1-mini, a different model from both compared versions (gpt-5-mini and gpt-6-luna), so no model grades its own answers, and the same judge for both runs. 8 verdicts were checked by hand: all 5 "correct" were right; 1 of 3 "incorrect" was right, the other 2 came from a too-narrow reference and an ambiguous question (20/40 acuity under SC 1.4.6). The judge is sometimes too strict, never too lenient. A judge bug (list numbers "1.", "2." counted as uncited claims) was found and fixed.

**Results (all 122 questions, same judge; `eval/results/compare_baseline_mini_vs_e8v2.md`):**

| Metric | Baseline (gpt-5-mini, default effort) | Final (E8 + citation fix v2) | Change |
|---|---|---|---|
| Accuracy | 73.8% | **80.3%** | +6.6 pts |
| Accuracy (partial = 0.5) | 79.1% | 86.9% | +7.8 pts |
| "I don't know" accuracy | 86.1% | 95.1% | +9.0 pts |
| False "I don't know" (answerable refused) | 16 | 4 | |
| Faithfulness | 98.9% | 97.1% | −1.8 pts |
| Citation accuracy | 99.1% | 98.6% | −0.5 pts |
| Cost per request | $0.003214 | **$0.000404** | **−87%** |
| Latency p50 / p95 | 24.7 s / 34.7 s | 9.4 s / 12.8 s | −62% / −63% |

Both Week 8 targets are met (cost or p95 −50%, at most 2 accuracy points lost). The first E8 run had faithfulness 90.9%: most unsupported claims were correct but uncited opening sentences ("Yes."), plus off-topic refusals not detected as "I don't know". The citation fix v2 brought it back to 97.1%. With 122 questions one question is 0.8 points, so +6.6 points (8 questions) supports "no accuracy lost" rather than a precise gain.

**Threshold sweep.** The saved baseline answers were replayed with `MIN_SCORE` from 0 to 6, with no new LLM calls: raising it only adds false "I don't know" answers (16 to 18) and blocks no extra off-topic question (those are already stopped by the rewrite), so 0 is kept. Thresholds below 0 cannot be simulated, because the run never asked the LLM for those questions.

## 8. Known failure cases and limitations

Observed in retrieval:
1. **Spec vs Understanding pages:** the specification page can outrank the Understanding page that answers a question (for example "What does Level AAA add for synchronized media?").
2. **Techniques crowd out Understanding pages** for general questions, because there are 436 Techniques pages and 120 Understanding pages.
3. **Off-topic questions still return results** ("capital of France" returned three unrelated technique pages), so refusing needs a score threshold on the reranker.
4. **The reranker broke 3 questions at k=5**: skipping repeated content, non-text content in electronic text, and activating an image link by script. [To check whether it returned another valid passage.]
5. **Repeated text is stored once:** a glossary entry shared by many pages is only retrievable from the first page that contained it.
6. **Tables, code blocks and cross-references** between success criteria are flattened to text.

Observed in the answers (generation eval):
7. **False "I don't know":** the model refuses although the right chunk is retrieved (rerank score 7 to 9), e.g. "How can an online test be calibrated to avoid timing affecting scores?". 4 in the final version, 16 in the baseline.
8. **Refusals not detected:** an off-topic refusal written as "The sources do not explain… I don't know." is not caught, because the check looks at the start of the answer (2 of 12 off-topic questions in the final version).
9. **Incomplete answers:** with low reasoning effort, answers are shorter and more often "partial" (16), e.g. Technique G5 without the auction details.
10. **Small factual slips:** for the question on a text color without a background color, both versions added a sentence about a default white background that the judge found unsupported by the cited chunk.

Limitations of the evaluation:
- The embedding model (all-MiniLM-L6-v2) reads only the first 256 word-pieces of a chunk. The median chunk is 92 words, but about 23% of chunks are longer than 190 words, so the end of those chunks is not in the vector. BM25 and the reranker still see the whole chunk.
- The questions were drafted from the passages, so they share words with their answers. This probably favours BM25 over vector search. Questions written by people are the check. We did not have time to add a hand-written subset, so the recall numbers for BM25 may be a little optimistic.
- With 110 questions, one question is 0.9 points and the 95% interval is about plus or minus 6 points, so small differences are not significant.
- Several questions can be answered from two pages (an Understanding page and a Technique page) but are scored against one.
- Latencies depend on the machine.
- The chunk-size experiment used the earlier 33-question set and page-level recall.
- The LLM judge has errors (see section 7); a few gold answers are narrower than the documents, which makes accuracy slightly pessimistic.

## 9. Reproduce

```
pip install -r requirements.txt
python eval/smoke_test.py      # checks the data, the index and a few canary searches
python eval/ablation.py        # the table in section 4
python -m src.scrape && python -m src.chunk && python -m src.index   # rebuild everything (about 10 minutes)
python eval/chunk_experiment.py --file data/eval.jsonl               # the table in section 2
python -m eval.generation_eval summary --version baseline_mini       # section 7, from the saved answers (no LLM calls)
python -m eval.generation_eval compare baseline_mini e8v2            # the before/after table
python -m eval.generation_eval threshold --version baseline_mini     # the threshold sweep
```
