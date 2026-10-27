# The Librarian - WCAG 2.2 assistant (CS496 Project 2)

A RAG chatbot that answers accessibility questions from WCAG 2.2 (spec, Understanding, Techniques),
cites its sources, and says "I don't know" when the answer is not in the documents.

Part of the AIEngineering2026 repo. Run every command from inside this folder (project2-librarian/).

Team: <You>, Khadija, Maya

## Setup (one command)
    pip install -r requirements.txt && cp .env.example .env

## Build the index
    python -m src.scrape      # download pages to data/raw
    python -m src.chunk       # writes data/chunks.jsonl
    python -m src.index       # builds BM25 + Chroma in data/index

## Run
    streamlit run src/app.py

## Evaluate
    python eval/retrieval_eval.py
    python eval/generation_eval.py
    python eval/ablation.py

## Layout
    src/        scrape, chunk, index, retrieve, pipeline, app
    data/       chunks.jsonl, eval.jsonl (questions + source passages)
    eval/       retrieval eval, generation eval, ablation
    docs/       design.md, optimisation.md, postmortem.md

## Results
(TBD: ablation table, faithfulness, latency, cost)

## Contributions
- <You>: data collection, chunking, index, retrieve()
- Khadija: pipeline, reranker, LLM prompt, UI, deploy
- Maya: eval set, eval scripts, docs, report

## Git rules
- One branch per person: `p2-data-index`, `p2-pipeline`, `p2-eval`. Open PRs into `main`. Only touch project2-librarian/ so other projects are not affected.
- Commit small and often. Never commit `.env` or API keys.
- Shared formats: see data/FORMATS.md
