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

**Generation** (LLM judge, subset of [30] questions): see `eval/results/generation_*.md` and the report.
[accuracy / faithfulness / citation accuracy]

**Week 8 optimisation** ("low" reasoning effort for both LLMs):

| | Before | After |
|---|---|---|
| Cost per request | $0.000574 | **$0.000268 (−53%)** |
| p50 / p95 latency | 6.43 s / 11.64 s | 3.28 s / 10.49 s |
| Hard test set (15 questions) | 14/15 | 14/15 |
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

- **Mayssa (data & index):** document ingestion and preprocessing, text chunking, index construction,
  implementation of the core `retrieve()` function, evaluation tooling (question generation and
  retrieval ablation), retrieval experiments comparing keyword, vector, hybrid, and reranked retrieval,
  and chunk-size evaluation.
- **Khadija (pipeline, UI & optimisation):** answer pipeline (question rewriting, reranking, generation
  with citations, two-layer "I don't know"), FastAPI server and web interface, hard test set,
  latency/cost measurement and Week 8 experiment runner and optimisation (−53% cost), review of all
  eval questions, postmortem, optimisation report.
- **Maya (evaluation & documentation):**
  - `eval/retrieval_eval.py`: recall@1/3/5/10, MRR@10 and search latency (p50/p95). A hit means a
    retrieved chunk contains the gold source passage, not just the same URL (the whole WCAG 2.2 spec is
    one URL, so URL matching inflates the score; the URL-only number is reported separately and labelled).
    Boilerplate passages that W3C repeats on many pages only count on their own page.
  - `eval/ablation.py`: BM25 only / vector only / hybrid / hybrid + reranker (+ optional full pipeline
    with question rewriting); report table in `eval/results/ablation.md`.
  - `eval/generation_eval.py`: LLM judge (gpt-oss-20b) for correctness vs the reference answer,
    faithfulness (claims supported by the chunks they cite), citation accuracy and "I don't know"
    accuracy. Answers are saved first and judged from the file; both steps resume after Groq's daily
    limit. Includes the Week 8 before/after comparison (`compare`, 2-point rule) and an "I don't know"
    threshold sweep.
  - `eval/feedback_summary.py`: summary of the website's 👍/👎 votes for the report.
  - Eval set: question drafting and review (`data/review/maya.jsonl`).
- **All:** eval question review, report, postmortem.