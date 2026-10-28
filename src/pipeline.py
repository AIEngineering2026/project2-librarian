"""KHADIJA: answer(question) -> {"answer": str, "citations": [chunk ids], "chunks": [...]}.

Steps:
    1. rewrite the question into clear English WCAG search queries (small, cheap LLM)
       -> fixes vague questions, typos, other languages, and multi-part questions
    2. retrieve candidates for the original question + each rewritten query (Mayssa's hybrid search)
    3. rerank all candidates with a cross-encoder and keep the best 5
    4. if even the best chunk scores too low -> "I don't know" (no answer LLM call, saves money)
    5. LLM answers ONLY from those 5 chunks, citing them as [1], [2]...
    6. turn [1], [2] back into real chunk ids

Quick test from the project root:  py -m src.pipeline
"""
import json
import os
import re

from dotenv import load_dotenv
from groq import Groq
from sentence_transformers import CrossEncoder

from src.retrieve import retrieve

load_dotenv()  # reads GROQ_API_KEY from .env
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

MODEL = "openai/gpt-oss-120b"          # writes the answer
REWRITE_MODEL = "openai/gpt-oss-20b"   # rewrites the question (smaller = cheaper and faster)
RERANKER = "cross-encoder/ms-marco-MiniLM-L-6-v2"
CANDIDATES = 20    # chunks fetched when there is only one search query
PER_QUERY = 10     # chunks fetched per query when there are several
TOP_K = 5          # chunks kept and sent to the answer LLM
MIN_SCORE = 0.0    # "I don't know" threshold on the reranker score (to tune with Maya's eval)
IDK = "I don't know."

REWRITE_PROMPT = """You prepare search queries for a search engine over the official WCAG 2.2
documents (W3C, written in English). You do NOT answer the question.

Reply with ONLY a JSON object, no other text:
{"language": "...", "question_en": "...", "queries": ["...", "..."]}
- language: the language the user wrote in, in English (e.g. "English", "French", "Arabic").
- question_en: the user's question as one clear, standalone English question
  (translate it if it is not in English, fix typos).
- queries: 1 to 3 short English search queries that use official WCAG vocabulary
  (e.g. "target size", "contrast ratio", "cognitive function test", "non-text contrast").
  If the question has several parts, write one query per part.
  Include a success criterion number ONLY if you are sure it is correct.
  NEVER put numbers or values that could be the answer (ratios, pixel sizes, durations)
  in the queries."""

SYSTEM_PROMPT = """You are a WCAG 2.2 accessibility assistant for developers.
Rules:
1. Answer ONLY using the numbered sources given to you. Never use outside knowledge.
2. After every fact, cite the source number in normal ASCII square brackets, like [1] or [2][3].
3. If the sources do not contain the answer, reply exactly: I don't know.
4. Read the sources carefully: if a source says something is EXEMPT or an EXCEPTION applies,
   say so. Never state a requirement that the sources do not state for that exact case.
5. Requirements often differ by conformance level (A, AA, AAA). Always name the level and the
   success criterion for each requirement, and never mix values from different levels.
   Unless the user asks about AAA, give the Level AA requirement first.
6. Keep the answer short and clear (2-5 sentences, or a short list).
7. Write the answer in the language given in "Answer language"."""

_reranker = None


def get_reranker():
    """Load the reranker model once, the first time we need it."""
    global _reranker
    if _reranker is None:
        _reranker = CrossEncoder(RERANKER)
    return _reranker


def rewrite(question):
    """Ask a small LLM for a clean English question + 1-3 search queries.
    If anything goes wrong, fall back to the original question (the pipeline still works)."""
    tokens = {"prompt": 0, "completion": 0}
    try:
        # No JSON mode: Groq's JSON mode sometimes fails with gpt-oss ("json_validate_failed"),
        # so we ask for JSON in the prompt and extract the {...} part ourselves.
        response = client.chat.completions.create(
            model=REWRITE_MODEL,
            temperature=0,
            messages=[{"role": "system", "content": REWRITE_PROMPT},
                      {"role": "user", "content": question}],
        )
        u = getattr(response, "usage", None)
        if u:
            tokens = {"prompt": u.prompt_tokens, "completion": u.completion_tokens}
        raw = response.choices[0].message.content or ""
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        data = json.loads(match.group(0)) if match else {}
        language = str(data.get("language") or "English").strip()
        question_en = str(data.get("question_en") or question).strip()
        queries = [str(q).strip() for q in data.get("queries", []) if str(q).strip()][:3]
        return language, question_en, queries or [question_en], tokens
    except Exception as e:
        print(f"[rewrite] failed, using the original question: {e}")
        return "English", question, [question], tokens


def gather_candidates(searches):
    """Run the search for every query and merge the results (no duplicates)."""
    per_query = CANDIDATES if len(searches) == 1 else PER_QUERY
    merged = {}
    for q in searches:
        for c in retrieve(q, k=per_query):
            merged.setdefault(c["id"], dict(c))
    return list(merged.values())


def rerank(queries, chunks, top_k=TOP_K):
    """Score every chunk against every query; a chunk's score is its BEST score.
    (So for a two-part question, chunks for part 2 are not pushed out by chunks for part 1.)"""
    if not chunks:
        return []
    texts = [f"{c['title']} - {c['section']}\n{c['text']}" for c in chunks]
    pairs = [(q, t) for q in queries for t in texts]
    scores = get_reranker().predict(pairs)
    n = len(chunks)
    for i, c in enumerate(chunks):
        c["rerank_score"] = float(max(scores[j * n + i] for j in range(len(queries))))
    return sorted(chunks, key=lambda c: c["rerank_score"], reverse=True)[:top_k]


def build_sources_text(chunks):
    """Number the chunks [1], [2]... so the LLM can cite them with short tags."""
    parts = []
    for i, c in enumerate(chunks, start=1):
        parts.append(f"[{i}] {c['title']} - {c['section']}\n{c['text']}")
    return "\n\n".join(parts)


# Matches [1], [1, 2], 【1】 and 【1†L1-L4】 (formats the model sometimes produces)
CITATION_RE = re.compile(r"[\[【]\s*(\d+(?:\s*,\s*\d+)*)\s*(?:†[^\]】]*)?[\]】]")


def normalize_citations(text):
    """Rewrite 【1】 or [1, 2] as [1] / [1][2] so every answer looks the same."""
    return CITATION_RE.sub(lambda m: "".join(f"[{n.strip()}]" for n in m.group(1).split(",")), text)


def extract_citations(text, chunks):
    """Find [1], [2]... in the answer and turn them into real chunk ids (no duplicates)."""
    ids = []
    for n in re.findall(r"\[(\d+)\]", normalize_citations(text)):
        i = int(n) - 1
        if 0 <= i < len(chunks) and chunks[i]["id"] not in ids:
            ids.append(chunks[i]["id"])
    return ids


def answer(question: str) -> dict:
    # 1. rewrite
    language, question_en, queries, rewrite_tokens = rewrite(question)
    searches = list(dict.fromkeys([question, *queries]))   # original first, no duplicates

    # 2-3. search + rerank
    candidates = gather_candidates(searches)
    chunks = rerank(list(dict.fromkeys([question_en, *queries])), candidates)
    top_score = chunks[0]["rerank_score"] if chunks else None

    result = {
        "answer": IDK, "citations": [], "chunks": chunks,
        "rewrite": {"language": language, "question_en": question_en, "queries": queries},
        "top_score": top_score, "idk_reason": None,
        "usage": {"prompt": 0, "completion": 0,
                  "rewrite_prompt": rewrite_tokens["prompt"], "rewrite_completion": rewrite_tokens["completion"]},
    }

    # 4. "I don't know" rule: nothing relevant enough -> don't even call the answer LLM
    if top_score is None or top_score < MIN_SCORE:
        result["idk_reason"] = "low_score"
        return result

    # 5. answer
    user_msg = f"Sources:\n{build_sources_text(chunks)}\n\nQuestion: {question}"
    if question_en.lower() != question.lower():
        user_msg += f"\n(In clear English: {question_en})"
    user_msg += f"\nAnswer language: {language}"
    response = client.chat.completions.create(
        model=MODEL,
        temperature=0,
        messages=[{"role": "system", "content": SYSTEM_PROMPT},
                  {"role": "user", "content": user_msg}],
    )
    text = normalize_citations((response.choices[0].message.content or "").strip())
    u = getattr(response, "usage", None)
    if u:
        result["usage"]["prompt"], result["usage"]["completion"] = u.prompt_tokens, u.completion_tokens

    if text.lower().startswith("i don't know"):
        result["idk_reason"] = "llm_said_idk"
        return result

    # 6. citations
    result["answer"] = text
    result["citations"] = extract_citations(text, chunks)
    return result


if __name__ == "__main__":
    for q in ["What is the minimum contrast for normal text?",
              "buttons too small?",
              "What is the best pizza in Tunis?"]:
        r = answer(q)
        print("\n==============================")
        print("Q:", q)
        print("Rewritten:", r["rewrite"]["question_en"], "|", r["rewrite"]["queries"])
        print("Top chunks after reranking:")
        for c in r["chunks"]:
            print(f"  {c['rerank_score']:6.2f}  {c['id']}")
        print("A:", r["answer"], f"({r['idk_reason']})" if r["idk_reason"] else "")
        print("Cited:", r["citations"])