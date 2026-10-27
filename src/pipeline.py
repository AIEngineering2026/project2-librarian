"""KHADIJA: answer(question) -> {"answer": str, "citations": [chunk ids], "chunks": [...]}.
Steps: (optional rewrite) -> retrieve(k=20) -> rerank -> top 5 -> LLM (answer ONLY from chunks, cite) -> "I don't know"."""
from src.retrieve import retrieve

def answer(question: str) -> dict:
    raise NotImplementedError("Khadija: implement rerank + LLM call + IDK threshold")
