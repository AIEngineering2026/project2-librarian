"""KHADIJA: web server. Serves the page (web/index.html) and the API it calls.

Run from the project root:   py -m uvicorn src.server:app --reload
Then open:                   http://127.0.0.1:8000

Endpoints
    GET  /              -> the web page
    POST /api/ask       -> {"question": "..."}  -> answer + sources + passages + latency
    POST /api/feedback  -> {"question", "answer", "helpful"} -> saved to data/feedback.jsonl
"""
import json
import math
import re
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from src.pipeline import IDK, answer, get_reranker
from src.retrieve import retrieve

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / "web" / "index.html"
FEEDBACK_FILE = ROOT / "data" / "feedback.jsonl"

SC_RE = re.compile(r"\b([1-4])\.(\d{1,2})\.(\d{1,2})\b")
PRINCIPLES = {"1": "Perceivable", "2": "Operable", "3": "Understandable", "4": "Robust"}


@asynccontextmanager
async def lifespan(app):
    # Load the search index and the reranker once at startup,
    # so the first visitor doesn't wait for the models to load.
    retrieve("warm up", k=1)
    get_reranker()
    yield


app = FastAPI(title="The Librarian", lifespan=lifespan)


class AskIn(BaseModel):
    question: str = Field(min_length=1, max_length=500)


class FeedbackIn(BaseModel):
    question: str = Field(max_length=500)
    answer: str = Field(max_length=5000)
    helpful: bool


def find_sc(chunk):
    """Find the success criterion number (e.g. 1.4.3) in the chunk's title/section/start of text."""
    where = f"{chunk.get('title', '')} {chunk.get('section', '')} {chunk.get('text', '')[:200]}"
    m = SC_RE.search(where)
    return m.group(0) if m else None


def page_kind(chunk_id):
    """Which W3C document the chunk comes from, from its id prefix."""
    if "understanding" in chunk_id:
        return "Understanding"
    if "techniques" in chunk_id:
        return "Technique"
    if chunk_id.startswith("tr-"):
        return "WCAG 2.2 Recommendation"
    return "W3C"


def to_passage(n, chunk, cited_ids):
    score = float(chunk.get("rerank_score", 0.0))
    sc = find_sc(chunk)
    return {
        "n": n,  # matches the [n] in the answer
        "id": chunk["id"],
        "title": chunk.get("title", ""),
        "section": chunk.get("section", ""),
        "url": chunk.get("url", ""),
        "text": chunk.get("text", ""),
        "kind": page_kind(chunk["id"]),
        "sc": sc,
        "principle": PRINCIPLES.get(sc[0]) if sc else None,
        "score": round(score, 2),
        "relevance": round(100 / (1 + math.exp(-score))),  # reranker score -> 0-100 for the bar
        "cited": chunk["id"] in cited_ids,
    }


@app.get("/")
def home():
    return FileResponse(PAGE)


@app.post("/api/ask")
def ask(body: AskIn):
    question = body.question.strip()
    start = time.perf_counter()
    try:
        result = answer(question)
    except Exception as e:  # e.g. Groq is down or the key is missing
        raise HTTPException(status_code=502, detail=f"The answer service failed: {e}")
    latency_ms = round((time.perf_counter() - start) * 1000)

    cited = set(result["citations"])
    passages = [to_passage(i, c, cited) for i, c in enumerate(result["chunks"], start=1)]
    return {
        "question": question,
        "answer": result["answer"],
        "idk": result["answer"] == IDK,
        "latency_ms": latency_ms,
        "sources": [p for p in passages if p["cited"]],
        "passages": passages,
    }


@app.post("/api/feedback")
def feedback(body: FeedbackIn):
    FEEDBACK_FILE.parent.mkdir(parents=True, exist_ok=True)
    row = {"time": datetime.now(timezone.utc).isoformat(), **body.model_dump()}
    with open(FEEDBACK_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return {"ok": True}