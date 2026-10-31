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
import time

from dotenv import load_dotenv
from openai import OpenAI
from sentence_transformers import CrossEncoder

from src.retrieve import retrieve

load_dotenv()  # reads the API keys (and optional overrides) from .env

# ---- LLM provider: "openai" (default) or "groq". Both use the OpenAI client (Groq is OpenAI-compatible). ----
PROVIDER = os.getenv("LLM_PROVIDER", "openai").lower()
PROVIDERS = {
    #           API key variable   base URL                          answer model           rewrite model          temperature
    "openai": ("OPENAI_API_KEY", None,                             "gpt-6-luna",          "gpt-5-nano",          None),
    "groq":   ("GROQ_API_KEY",   "https://api.groq.com/openai/v1", "openai/gpt-oss-120b", "openai/gpt-oss-20b",  0),
}
_key_var, _base_url, _answer_default, _rewrite_default, TEMPERATURE = PROVIDERS[PROVIDER]
client = OpenAI(api_key=os.getenv(_key_var), base_url=_base_url)

# Models can be overridden in .env, e.g. ANSWER_MODEL=gpt-6-luna
MODEL = os.getenv("ANSWER_MODEL", _answer_default)            # writes the answer
REWRITE_MODEL = os.getenv("REWRITE_MODEL", _rewrite_default)  # rewrites the question (smaller = cheaper)
# OpenAI's reasoning models (gpt-5-*) do not accept temperature, so it is only sent when set (Groq: 0).
RERANKER = "cross-encoder/ms-marco-MiniLM-L-6-v2"
CANDIDATES = 20    # chunks fetched when there is only one search query
PER_QUERY = 10     # chunks fetched per query when there are several
TOP_K = 5          # chunks kept and sent to the answer LLM
MIN_SCORE = 0.0    # "I don't know" threshold on the reranker score (to tune with Maya's eval)
IDK = "I don't know."

# ---- Week 8 optimisation switches (eval/experiment.py changes these per experiment) ----
# Final choice (see docs/optimisation.md): E1 + E6 = "low" reasoning for both models
# -> cost per request -53%, same hard-set accuracy. None = model default (the baseline).
REWRITE_EFFORT = "low"         # None = model default, or "minimal" (OpenAI) / "low" / "medium" / "high"
ANSWER_EFFORT = "low"          # same, for the answer model
SKIP_REWRITE_IF_CLEAR = False  # skip the rewrite call for clear English questions using WCAG words
USE_CACHE = False              # answer repeated questions from memory

# Words that show a question is already written in WCAG vocabulary (used by SKIP_REWRITE_IF_CLEAR)
WCAG_TERMS = [
    "wcag", "success criterion", "contrast", "target size", "focus", "keyboard", "caption",
    "alt text", "alternative text", "text alternative", "label", "heading", "reflow", "aria",
    "screen reader", "flash", "timing", "time limit", "captcha", "authentication", "error",
    "language", "lang attribute", "page title", "link purpose", "non-text", "audio", "video",
    "dragging", "pointer", "consistent help", "redundant entry", "resize text", "text spacing",
]
SC_NUMBER_RE = re.compile(r"\b[1-4]\.\d{1,2}\.\d{1,2}\b")

_cache = {}

REWRITE_PROMPT = """You prepare search queries for a search engine over the official WCAG 2.2
documents (W3C, written in English). You do NOT answer the question.

Reply with ONLY a JSON object, no other text:
{"off_topic": false, "language": "...", "question_en": "...", "queries": ["...", "..."]}
- off_topic: true ONLY if the question has nothing to do with web/digital accessibility, WCAG,
  disabilities and technology, or how websites/apps work for users (e.g. food, sport, travel).
  If off_topic is true, return an empty list of queries. Do NOT invent accessibility queries.
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
2. EVERY sentence (and every list item) must end with the number of the source that says it, in normal
   ASCII square brackets, like [1] or [2][3]. If you cannot cite a sentence, do not write it.
   Do not add summaries, conclusions or advice that no source states in words.
3. If the sources do not contain the answer, reply exactly: I don't know.
4. Read the sources carefully: if a source says something is EXEMPT or an EXCEPTION applies,
   say so. Never state a requirement that the sources do not state for that exact case.
5. Requirements often differ by conformance level (A, AA, AAA). Always name the level and the
   success criterion for each requirement, and never mix values from different levels.
   Unless the user asks about AAA, give the Level AA requirement first.
6. Keep the answer short and clear (2-5 sentences, or a short list).
7. Write the answer in the language given in "Answer language"."""

_reranker = None


def llm_options(effort):
    """Extra parameters for an LLM call: reasoning effort if set, temperature only if the provider accepts it."""
    options = {}
    if effort:
        options["reasoning_effort"] = effort
    if TEMPERATURE is not None:
        options["temperature"] = TEMPERATURE
    return options


def get_reranker():
    """Load the reranker model once, the first time we need it."""
    global _reranker
    if _reranker is None:
        _reranker = CrossEncoder(RERANKER)
    return _reranker


def rewrite(question):
    """Ask a small LLM for a clean English question + 1-3 search queries.
    If the reply is empty or broken, ask once more; if it fails again, fall back to the original
    question (the pipeline still works, but a non-English question is then searched in its own language)."""
    tokens = {"prompt": 0, "completion": 0, "attempts": 0, "failed": False}
    for attempt in (1, 2):
        tokens["attempts"] = attempt
        try:
            # No JSON mode: Groq's JSON mode sometimes fails with gpt-oss ("json_validate_failed"),
            # so we ask for JSON in the prompt and extract the {...} part ourselves.
            response = client.chat.completions.create(
                model=REWRITE_MODEL,
                messages=[{"role": "system", "content": REWRITE_PROMPT},
                          {"role": "user", "content": question}],
                **llm_options(REWRITE_EFFORT),
            )
            u = getattr(response, "usage", None)
            if u:   # count the tokens of every attempt (both are paid)
                tokens["prompt"] += u.prompt_tokens
                tokens["completion"] += u.completion_tokens
            raw = response.choices[0].message.content or ""
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            data = json.loads(match.group(0)) if match else {}
            if data.get("off_topic") is True:
                return (str(data.get("language") or "English").strip(),
                        str(data.get("question_en") or question).strip(), [], tokens)   # off-topic
            queries = [str(q).strip() for q in data.get("queries", []) if str(q).strip()][:3]
            if not queries:
                raise ValueError(f"no usable queries in the reply: {raw[:80]!r}")
            language = str(data.get("language") or "English").strip()
            question_en = str(data.get("question_en") or question).strip()
            return language, question_en, queries, tokens
        except Exception as e:
            print(f"[rewrite] attempt {attempt} failed: {e}")
    print("[rewrite] using the original question")
    tokens["failed"] = True   # recorded in the result so the evals can count how often this happens
    return "English", question, [question], tokens


def is_clear(question):
    """True if the question is plain English (ASCII) and already uses WCAG words or an SC number."""
    q = question.lower()
    return question.isascii() and (bool(SC_NUMBER_RE.search(q)) or any(t in q for t in WCAG_TERMS))


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


# Faithfulness guard: a sentence is split after . ! ? when the next one starts with a capital or a digit,
# or after a citation "]" followed by a capital (when the model puts [n] after the full stop).
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-ZÀ-ÖØ-Þ0-9\"(«])|(?<=\])\s+(?=[A-ZÀ-ÖØ-Þ])")
NO_CLAIM_RE = re.compile(r"i don't know|do not (say|state|mention|cover|address)|don't (say|state|mention|cover|address)"
                         r"|not (mentioned|covered|addressed|specified)", re.IGNORECASE)


def keep_cited_sentences(text):
    """Remove the uncited sentences at the END of the answer (the model's own conclusions or advice,
    e.g. "So: buttons smaller than 24x24 fail AA..."). Returns (new_text, number_removed).
    Uncited sentences BEFORE the last citation are kept: they are usually the main answer with a
    forgotten citation, and removing them would gut the answer. Sentences that only say the sources
    don't cover something are always kept. An answer with no citation at all is left unchanged."""
    cited = lambda s: re.search(r"\[\d+\]", s)
    lines = text.split("\n")
    last = max((i for i, line in enumerate(lines) if cited(line)), default=None)
    if last is None:
        return text, 0
    removed = 0
    # the last cited line: drop the uncited sentences that come after its last citation
    parts = SENTENCE_SPLIT_RE.split(lines[last])
    last_part = max(i for i, p in enumerate(parts) if cited(p))
    tail = parts[last_part + 1:]
    kept_tail = [p for p in tail if NO_CLAIM_RE.search(p)]
    removed += len(tail) - len(kept_tail)
    lines[last] = " ".join(parts[:last_part + 1] + kept_tail)
    # the lines after it: keep only the "sources don't cover this" sentences
    after = []
    for line in lines[last + 1:]:
        if not line.strip():
            continue
        parts = SENTENCE_SPLIT_RE.split(line)
        keep = [p for p in parts if NO_CLAIM_RE.search(p)]
        removed += len(parts) - len(keep)
        if keep:
            after.append(" ".join(keep))
    new_text = "\n".join(lines[:last + 1] + after).strip()
    return new_text, removed


def extract_citations(text, chunks):
    """Find [1], [2]... in the answer and turn them into real chunk ids (no duplicates)."""
    ids = []
    for n in re.findall(r"\[(\d+)\]", normalize_citations(text)):
        i = int(n) - 1
        if 0 <= i < len(chunks) and chunks[i]["id"] not in ids:
            ids.append(chunks[i]["id"])
    return ids


def answer(question: str) -> dict:
    # 0. cache (Week 8): same question asked before -> answer instantly, no LLM call
    key = " ".join(question.lower().split())
    if USE_CACHE and key in _cache:
        return {**_cache[key], "cached": True}

    timings = {}  # seconds spent in each step, to see where the time goes
    t = time.perf_counter()

    # 1. rewrite (skipped for clear questions when SKIP_REWRITE_IF_CLEAR is on)
    if SKIP_REWRITE_IF_CLEAR and is_clear(question):
        language, question_en, queries, rewrite_tokens = "English", question, [question], {"prompt": 0, "completion": 0}
    else:
        language, question_en, queries, rewrite_tokens = rewrite(question)
    timings["rewrite"] = time.perf_counter() - t; t = time.perf_counter()

    # 1b. off-topic question (e.g. "best pizza in Tunis"): stop here, no search, no answer LLM call.
    # Without this, the rewriter could invent WCAG queries that match real passages.
    if not queries:
        timings.update(search=0.0, rerank=0.0, answer=0.0)
        return _remember(key, {
            "answer": IDK, "citations": [], "chunks": [],
            "rewrite": {"language": language, "question_en": question_en, "queries": [],
                        "attempts": rewrite_tokens.get("attempts", 0), "failed": rewrite_tokens.get("failed", False)},
            "top_score": None, "idk_reason": "off_topic", "timings": timings,
            "usage": {"prompt": 0, "completion": 0,
                      "rewrite_prompt": rewrite_tokens["prompt"], "rewrite_completion": rewrite_tokens["completion"]},
        })

    searches = list(dict.fromkeys([question, *queries]))   # original first, no duplicates

    # 2-3. search + rerank
    candidates = gather_candidates(searches)
    timings["search"] = time.perf_counter() - t; t = time.perf_counter()
    chunks = rerank(list(dict.fromkeys([question_en, *queries])), candidates)
    timings["rerank"] = time.perf_counter() - t; t = time.perf_counter()
    top_score = chunks[0]["rerank_score"] if chunks else None

    result = {
        "answer": IDK, "citations": [], "chunks": chunks,
        "rewrite": {"language": language, "question_en": question_en, "queries": queries,
                    "attempts": rewrite_tokens.get("attempts", 0), "failed": rewrite_tokens.get("failed", False)},
        "top_score": top_score, "idk_reason": None, "timings": timings,
        "usage": {"prompt": 0, "completion": 0,
                  "rewrite_prompt": rewrite_tokens["prompt"], "rewrite_completion": rewrite_tokens["completion"]},
    }

    # 4. "I don't know" rule: nothing relevant enough -> don't even call the answer LLM
    if top_score is None or top_score < MIN_SCORE:
        result["idk_reason"] = "low_score"
        timings["answer"] = 0.0
        return _remember(key, result)

    # 5. answer
    user_msg = f"Sources:\n{build_sources_text(chunks)}\n\nQuestion: {question}"
    if question_en.lower() != question.lower():
        user_msg += f"\n(In clear English: {question_en})"
    user_msg += f"\nAnswer language: {language}"
    extra = llm_options(ANSWER_EFFORT)
    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "system", "content": SYSTEM_PROMPT},
                  {"role": "user", "content": user_msg}],
        **extra,
    )
    timings["answer"] = time.perf_counter() - t
    text = normalize_citations((response.choices[0].message.content or "").strip())
    u = getattr(response, "usage", None)
    if u:
        result["usage"]["prompt"], result["usage"]["completion"] = u.prompt_tokens, u.completion_tokens

    if text.lower().startswith("i don't know"):
        result["idk_reason"] = "llm_said_idk"
        return _remember(key, result)

    # 6. faithfulness guard: drop sentences that cite no source, then map citations to chunk ids
    text, result["uncited_removed"] = keep_cited_sentences(text)
    result["answer"] = text
    result["citations"] = extract_citations(text, chunks)
    return _remember(key, result)


def _remember(key, result):
    """Store the result in the cache (only used when USE_CACHE is on)."""
    if USE_CACHE:
        _cache[key] = result
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