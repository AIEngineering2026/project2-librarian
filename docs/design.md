# Design: The Librarian (WCAG 2.2 RAG assistant)

Short technical record of our design choices and why we made them.
Data and index sections: Mayssa. Pipeline: Khadija. Evaluation and failure cases: Maya.

---

## 1. Corpus and users

- **Corpus:** the official W3C WCAG 2.2 documentation (the Recommendation, *Understanding WCAG 2.2*, and
  *Techniques for WCAG 2.2*): 557 pages, split into 4,065 chunks.
- **Users:** front-end and mobile developers and UI designers. They ask in their own words ("buttons too
  small?") rather than in WCAG vocabulary ("target size"). That shaped the pipeline (§3.1).
- **Requirements:** answer only from the documents, cite every claim, say "I don't know" otherwise.

## 2. Chunking and index

### 2.1 Chunking (`src/chunk.py`)
1. Each page is split **by heading** (h2 / h3 / h4) first, so a chunk never mixes two sections. The page
   title and the section heading are kept as metadata with the URL.
2. Inside a section, whole **sentences / blocks** are packed up to a size limit (in words; ≈ 375 words ≈
   500 tokens). A sentence is only cut if it is longer than the limit on its own.
3. Each new chunk starts with the **last sentences of the previous one** (overlap, capped at a quarter of
   the chunk size), so a sentence cut at a boundary still appears whole in one chunk.
4. Chunks whose text already exists elsewhere are **dropped** (e.g. the *Key Terms* glossary that W3C
   repeats at the bottom of many pages).

**Cleaning history:** the same page existed under two URLs (`…/x` and `…/x.html`), so URL variants
were deduplicated, and repeated *Key Terms* sections flooded the results, so duplicates were removed
(4,749 → 4,522 → **4,065 chunks**).

### 2.2 Chunk size
*(Mayssa: sizes compared (300 / 500 / 800 tokens), recall@5 for each, and why the chosen size won.)*

| Chunk size | Chunks | Recall@5 (hybrid) | Recall@5 (hybrid + reranker) |
|---|---|---|---|
| 300 | | | |
| **500 (chosen)** | 4,065 | 0.87 | 0.93 |
| 800 | | | |

### 2.3 Index choice
- **BM25** (`rank_bm25`) for exact words: WCAG text is precise and technical (SC numbers, "target size",
  "contrast ratio"), so exact matches matter.
- **Vector search**: `all-MiniLM-L6-v2` embeddings (384 dimensions) in **Chroma**, cosine distance, for
  questions that use different words with the same meaning.
- **Why Chroma:** a local folder, no server, free, fast enough for 4k chunks (search ≈ 25 ms), and
  rebuilt from `chunks.jsonl` with one command. We did not need a database server for this size.
- **Hybrid:** the two rankings are merged with **reciprocal rank fusion** (1 / (60 + rank), summed).
  RRF scores only show the order, not confidence, so the "I don't know" threshold uses the reranker
  score instead.
*(Mayssa: anything to add on the index, e.g. the cloud version for Streamlit.)*

## 3. Pipeline design (`src/pipeline.py`)

```
question → rewrite (gpt-5-nano) → off-topic? → hybrid search (original + rewritten queries)
         → rerank (cross-encoder, best 5 of the candidates) → score < MIN_SCORE? → "I don't know"
         → answer with citations (gpt-6-luna) → drop uncited trailing sentences → web app
```

### 3.1 Question rewriting
A small model turns the question into a clean English question plus 1–3 WCAG search queries (fixes
vague wording, typos, French, SC numbers that BM25 splits). We always also search with the original
question, so a bad rewrite cannot remove good results. The rewriter may not put answer values in the
queries (it once invented "icons 4.5:1"). Off-topic questions ("best pizza in Tunis") are flagged by
the rewriter and stopped right away: no search, no answer call.

### 3.2 Reranking
A cross-encoder (`ms-marco-MiniLM-L-6-v2`) scores every (query, chunk) pair; each chunk keeps its best
score across the queries, so a two-part question keeps chunks for both parts. The best 5 are sent to
the answer model.

### 3.3 Answer and "I don't know"
The answer model gets the 5 chunks numbered [1]–[5] and must cite every sentence, report exceptions,
name the conformance level and never mix levels, and answer in the user's language. "I don't know" has
three layers: off-topic detection in the rewrite, the reranker threshold (`MIN_SCORE = 0`, kept after
the threshold sweep, §4.3), and the model's own refusal.

### 3.4 Models and cost (Week 8)
Final setting **E8**: gpt-6-luna answers and gpt-5-nano rewrites, both with "low" reasoning effort.
Against the baseline (gpt-5-mini, default effort): **cost −88%**, **p95 latency −64%**, accuracy
+1.6 points (full eval, §4.2). Details in `docs/optimisation.md`.

## 4. Evaluation (`eval/`)

### 4.1 Retrieval (`retrieval_eval.py`, `ablation.py`)
A retrieved chunk counts as a hit only if it **contains the gold passage** (substring, a run of ≥ 60%
of its words, or ≥ 85% of its words in order, after normalising case, quotes and spaces). We do not
match by URL: the whole WCAG 2.2 Recommendation is one URL (184 chunks), so URL matching inflates
recall. Boilerplate passages found on more than 3 pages only count on their own page.

| System | R@1 | R@5 | R@10 | MRR@10 |
|---|---|---|---|---|
| BM25 only | 0.59 | 0.85 | 0.92 | 0.69 |
| Vector only | 0.47 | 0.72 | 0.80 | 0.58 |
| Hybrid (RRF) | 0.56 | 0.87 | 0.96 | 0.69 |
| **Hybrid + reranker** | **0.72** | **0.93** | 0.96 | **0.80** |

Hybrid brings the right passage into the candidates; the reranker puts it first.

### 4.2 Generation (`generation_eval.py`)
Answers are generated once and saved, then an LLM judge (**gpt-4.1-mini**, a different model from
both compared versions) scores correctness against the gold answer, faithfulness (claims supported by
the chunks they cite), citation accuracy and "I don't know" accuracy. Full eval set: 124 questions
(112 answerable, 12 out of scope).

| Metric | Baseline (gpt-5-mini) | Final (E8) |
|---|---|---|
| Accuracy | 74.2% | 75.8% |
| "I don't know" accuracy | 86.3% | 95.2% |
| Faithfulness | 98.5% | 90.9% |
| Citation accuracy | 99.1% | 98.0% |
| Cost / request | $0.003208 | $0.000387 |
| p95 latency | 34.7 s | 12.6 s |

**Judge check:** 8 judgements checked by hand. All 5 "correct" verdicts were right; 1 of the 3
"incorrect" verdicts was right, the other 2 came from a too-narrow reference and an ambiguous test
question. So the judge is sometimes too strict, never too lenient.

### 4.3 "I don't know" threshold sweep
Saved answers replayed with `MIN_SCORE` from 0 to 6 (no new LLM calls): raising it only adds false
"I don't know" (16 → 18 on the baseline) and never blocks an extra off-topic question, so **0 is kept**.

## 5. Known failure cases

| Case | Example | Cause | Status |
|---|---|---|---|
| Uncited opening sentence | "Yes." before the cited explanation | The guard only removes uncited sentences at the **end** | Open: lowers faithfulness in E8 |
| Refusal not detected | "The sources do not state… I don't know." on an off-topic question | The check only looks at the **start** of the answer | Open (3 of 12 off-topic questions) |
| False "I don't know" | "Does SC 3.2.6 require help on downloaded PDFs?" (rerank score 9.6) | The model refuses although the right chunk is retrieved | Open (3 in E8, 16 in baseline) |
| Incomplete answers | Auction design for Technique G5 misses the details | Low reasoning effort gives shorter answers | 21 "partial" in E8 vs 4 in baseline |
| Correct but incomplete | Puzzle CAPTCHA → cites 1.1.1, misses 3.3.8 | The rewrite never searches "accessible authentication" | Open |
| Same text on several pages | Right text, retrieved from another page | WCAG repeats text across documents | Affects recall measurement |
| Test-set questions | "20/40 acuity under SC 1.4.6" mixes two criteria | Questions drafted from passages | A few flawed questions |
| Bias of the eval set | Questions reuse WCAG wording | Drafted from corpus passages | Favours BM25; real users are vaguer |
| Fixed earlier | Logo contrast answered "Yes" (logos are exempt); AA/AAA values mixed | Prompt rules on exceptions and levels | Fixed |

## 6. What we would do next
Cite the first sentence too (or apply the citation guard to leading sentences), detect "I don't know"
anywhere in a short answer, fix the few flawed eval questions, and make the reranker cheaper (it is now
the slowest step we control).
