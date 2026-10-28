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

## How it answers a question (`src/pipeline.py`)

| Step | What | Model / tool |
|---|---|---|
| 1. Rewrite | Clean English question + 1–3 WCAG search queries (fixes vague questions, typos, other languages, multi-part questions) | gpt-oss-20b (Groq) |
| 2. Search | Hybrid BM25 + vector search for the original question and each query | `src/retrieve.py` (rank_bm25 + Chroma, all-MiniLM-L6-v2) |
| 3. Rerank | Keep the 5 most relevant chunks | cross-encoder ms-marco-MiniLM-L-6-v2 |
| 4. "I don't know" | If the best rerank score < 0, no answer call | — |
| 5. Answer | Answer only from the 5 chunks, a citation `[n]` per claim, conformance level stated, same language as the question | gpt-oss-120b (Groq) |

## Tests and measurements

```bash
python -m eval.try_questions                              # 15 hard questions, printed
python -m eval.latency_cost                               # p50 / p95 latency and cost per request
python -m eval.experiment --label NAME [options]          # Week 8: speed + cost + accuracy in one run
```
`eval.experiment` options: `--rewrite-effort low`, `--answer-effort low`, `--top-k 3`, `--min-score 1.0`,
`--skip-rewrite-if-clear`, `--cache`. Results go to `eval/results/NAME.json` and `eval/results/experiments.md`.

**Note:** the Groq free tier allows 200,000 tokens per day for gpt-oss-120b (≈ 130 questions).
One experiment uses ≈ 50,000 tokens.

## Results (baseline, before Week 8)

| Metric | Value |
|---|---|
| p50 / p95 latency | 4.3 s / 11.5 s |
| Cost per request | $0.00052 (≈ $78/month at 100× = 5,000 requests/day) |
| Hard test set (15 questions) | 14/15 |

See `docs/optimisation.md` for Week 8 results.

## Contributions

- **Khadija:** answer pipeline (question rewriting, reranking, generation with citations, "I don't know"
  logic), FastAPI server and web interface, hard test set, latency/cost measurement and Week 8
  experiment runner, postmortem and optimisation report, review of the eval questions.
- **Mayssa:** *(to complete)*
- **Maya:** *(to complete)*