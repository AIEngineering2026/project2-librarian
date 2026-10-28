# 📚 The Librarian: a cited WCAG 2.2 assistant

A retrieval-augmented (RAG) question-answering service over the official **W3C WCAG 2.2**
documentation (557 pages: the Recommendation, *Understanding WCAG 2.2* and *Techniques for WCAG 2.2*).
It answers developers' accessibility questions **only from the official documents**, **cites every
claim**, and says **"I don't know"** when the documents do not contain the answer.

CS496 AI Engineering · Project 2 · Dr Abdeldjalil Labed · MedTech · Fall 2026

---

## Setup

```bash
pip install -r requirements.txt     # Windows: py -m pip install -r requirements.txt
python -m src.index                 # build the search index once (BM25 + Chroma)
```
Create a `.env` file in the project root with your Groq key (never commit it):
```
GROQ_API_KEY=gsk_...
```

## Run

```bash
python -m uvicorn src.server:app    # then open http://127.0.0.1:8000
```
- To share it on your local network: add `--host 0.0.0.0 --port 8000` and open `http://<your-ip>:8000`.
- To get a temporary public link: `cloudflared tunnel --url http://localhost:8000`.

**API:** `POST /api/ask` with `{"question": "..."}` returns the answer, citations, retrieved passages and
latency. `POST /api/feedback` with `{"question", "answer", "helpful"}` saves 👍/👎 to `data/feedback.jsonl`.

## How it answers a question

| Step | What | Model / tool |
|---|---|---|
| 0. Index (offline) | 557 W3C pages → 4,065 chunks with title / section / URL; BM25 + vector index | `src/scrape.py`, `src/chunk.py`, `src/index.py` |
| 1. Rewrite | Clean English question + 1–3 WCAG search queries (fixes vague questions, typos, other languages, multi-part questions) | gpt-oss-20b (Groq) |
| 2. Search | Hybrid BM25 + vector search (RRF) for the original question and each query | `src/retrieve.py` (rank_bm25 + Chroma, all-MiniLM-L6-v2) |
| 3. Rerank | Keep the 5 most relevant chunks | cross-encoder ms-marco-MiniLM-L-6-v2 |
| 4. "I don't know" | If the best rerank score < 0, stop without calling the answer model | — |
| 5. Answer | Answer only from the 5 chunks, a citation `[n]` per claim, conformance level stated, same language as the question | gpt-oss-120b (Groq) |

## Results

**Retrieval** (112 answerable eval questions; a hit = a retrieved chunk contains the gold passage):

| System | R@1 | R@5 | R@10 | MRR@10 | Search p50 |
|---|---|---|---|---|---|
| BM25 only | 0.59 | 0.85 | 0.92 | 0.69 | 12 ms |
| Vector only | 0.47 | 0.72 | 0.80 | 0.58 | 9 ms |
| Hybrid | 0.56 | 0.87 | 0.96 | 0.69 | 24 ms |
| **Hybrid + reranker** | **0.72** | **0.93** | **0.96** | **0.80** | 803 ms |

**Generation** (LLM judge gpt-oss-20b, first 30 questions of `data/eval.jsonl`, final version):

| Accuracy | Faithfulness | Citation accuracy | "I don't know" accuracy | Out-of-scope answered |
|---|---|---|---|---|
| 96.7% | 86.4% | 97.8% | 96.7% | 0 / 4 |

**Week 8 optimisation** ("low" reasoning effort for both LLMs):

| | Before | After |
|---|---|---|
| Cost per request | $0.000574 | **$0.000268 (−53%)** |
| p50 / p95 latency | 6.43 s / 11.64 s | 3.28 s / 10.49 s |
| Hard test set (15 questions) | 14/15 | 14/15 |
| Generation accuracy (30 questions, LLM judge) | 90.0% | 96.7% (no loss ✅) |
| Monthly LLM cost at 100× (5,000 requests/day) | ≈ $86 | ≈ $40 |

Details: `docs/optimisation.md` · failure cases: `docs/postmortem.md` · report: `docs/report.md`.

## Evaluation and measurement scripts

```bash
python -m eval.retrieval_eval                             # recall@k: bm25 / vector / hybrid
python -m eval.ablation                                   # + hybrid + reranker (no LLM calls)
python -m eval.generation_eval answer --version NAME      # run the pipeline on data/eval.jsonl
python -m eval.generation_eval judge  --version NAME      # LLM judge: correctness, faithfulness, citations
python -m eval.generation_eval compare baseline optimised # Week 8 before/after accuracy
python -m eval.feedback_summary                           # user feedback (👍/👎)
python -m eval.try_questions                              # 15 hard questions, printed
python -m eval.latency_cost                               # p50 / p95 latency and cost per request
python -m eval.experiment --label NAME [options]          # Week 8: speed + cost + accuracy in one run
```
`eval.experiment` options: `--rewrite-effort`, `--answer-effort`, `--top-k`, `--min-score`,
`--skip-rewrite-if-clear`, `--cache`. Results go to `eval/results/`.

**Note:** the Groq free tier allows 200,000 tokens per day for gpt-oss-120b (≈ 130 questions).

## Repository

```
src/        scrape.py, chunk.py, index.py, retrieve.py   (data & index)
            pipeline.py, server.py                       (answering & API)
web/        index.html                                   (web interface)
data/       chunks.jsonl, eval.jsonl, review/            (corpus chunks, eval questions)
eval/       retrieval_eval.py, ablation.py, generation_eval.py, feedback_summary.py,
            experiment.py, latency_cost.py, try_questions.py, review_tool.py, results/
docs/       report.md, design.md, optimisation.md, postmortem.md
```

## Contributions

**Mayssa (data & index)**
- Document ingestion and preprocessing: scraping the 557 W3C pages with title, section and URL.
- Cleaning and text chunking: URL-variant deduplication, removal of repeated sections (4,065 chunks).
- Index construction: BM25 + Chroma (`src/index.py`).
- Core `retrieve()` function with keyword, vector and hybrid search (`src/retrieve.py`).
- Evaluation tooling (question generation, retrieval ablation), retrieval experiments and chunk-size evaluation.

**Khadija (pipeline, interface & optimisation)**
- Answer pipeline (`src/pipeline.py`): question rewriting, reranking, generation with citations,
  two-layer "I don't know".
- FastAPI server and web interface (`src/server.py`, `web/index.html`).
- Hard test set, latency/cost measurement and Week 8 experiment runner (`eval/experiment.py`).
- Week 8 optimisation: −52% cost per request with no accuracy lost.
- Review of all eval questions; postmortem and optimisation report.

**Maya (evaluation & documentation)**
- Retrieval eval (`eval/retrieval_eval.py`): recall@k, MRR@10 and search latency, with passage-level
  matching instead of URL matching.
- Ablation (`eval/ablation.py`): BM25 / vector / hybrid / hybrid + reranker.
- Generation eval with an LLM judge (`eval/generation_eval.py`): correctness, faithfulness, citation
  accuracy, "I don't know" accuracy, Week 8 before/after comparison.
- User feedback summary (`eval/feedback_summary.py`).
- Eval question drafting and review.

**All:** eval question review, report, postmortem.