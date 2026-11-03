"""MAYA - T3/T4. Generation eval: correctness, faithfulness, citation accuracy, "I don't know" accuracy.

Two phases, so a judge crash never costs the (expensive) answers again:
  1. answer : run pipeline.answer() once per question -> eval/results/answers_<version>.jsonl
  2. judge  : LLM judge (default gpt-5, see below) reads that file -> eval/results/judged_<version>.jsonl
              + summary eval/results/generation_<version>.json / .md
Both phases RESUME: run the same command again and finished questions are skipped
(useful when a token limit or quota stops you halfway).

Run from the project root:
    py -m eval.generation_eval answer --version baseline
    py -m eval.generation_eval judge  --version baseline
    py -m eval.generation_eval answer --version optimised --set REWRITE_EFFORT='"low"' --set TOP_K=3
    py -m eval.generation_eval judge  --version optimised
    py -m eval.generation_eval compare baseline optimised     # Week 8 before/after table (+ the 2-point rule)
    py -m eval.generation_eval threshold --version baseline   # "I don't know" threshold sweep, no LLM calls
    py -m eval.generation_eval show --version baseline --n 10  # print judged answers to check the judge by hand
    py -m eval.generation_eval summary --version baseline     # recompute the scores from the saved files (no LLM calls)
Options: --limit N (first N questions only, for a quick test), --judge-model, --sleep SECONDS.

Keys (.env): the pipeline's key (OPENAI_API_KEY since the switch to OpenAI). The judge uses OPENAI_JUDGE_API_KEY
if set, else OPENAI_API_KEY (or GROQ_JUDGE_API_KEY / GROQ_API_KEY for a Groq judge model such as
"openai/gpt-oss-20b"). Judge model: --judge-model, or JUDGE_MODEL=... in .env, default gpt-5. It should NOT be
the model that writes the answers (a model tends to grade its own answers too kindly); the script warns if it is.
Settings changed with --set must already exist in src/pipeline.py
(the script stops if they don't, so a typo can't silently evaluate the baseline twice).

Metrics (all in the summary):
  accuracy          headline number for the Week 8 rule: answerable -> judge says "correct";
                    unanswerable -> answered "I don't know". Over ALL questions. ("partial" = 0 here;
                    accuracy_lenient counts it as 0.5.)
  correctness       answerable only: correct / partial / incorrect / refused ("I don't know")
  idk_accuracy      answerable -> must not refuse; unanswerable -> must refuse. Over all questions.
  faithfulness      answered questions: share of factual claims supported by the chunks they CITE
                    (a factual claim with no citation counts as unsupported). Also: % of answers fully faithful.
  citation_accuracy every [n] in every answer: does chunk n (= r["chunks"][n-1]) say what the sentence claims?
"""
import argparse
import ast
import contextlib
import io
import json
import os
import re
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

RESULTS = ROOT / "eval" / "results"
EVAL_FILE = ROOT / "data" / "eval.jsonl"
JUDGE_MODEL = "gpt-5"   # different from the answer model (gpt-5-mini); override with --judge-model or JUDGE_MODEL in .env
SETTINGS = ["PROVIDER", "MODEL", "REWRITE_MODEL", "RERANKER", "CANDIDATES", "PER_QUERY", "TOP_K", "MIN_SCORE",
            "REWRITE_EFFORT", "ANSWER_EFFORT", "SKIP_REWRITE_IF_CLEAR", "USE_CACHE"]       # recorded with every run if they exist in src/pipeline.py


# ====================================================================== small helpers
def read_jsonl(path):
    if not Path(path).exists():
        return []
    return [json.loads(l) for l in open(path, encoding="utf-8-sig") if l.strip()]


def append_jsonl(path, row):
    with open(path, "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def is_idk(text):
    """'I don't know.' / 'I don't know' / curly apostrophe / 'I do not know' -> True."""
    t = (text or "").strip().lower().replace("’", "'")
    return t.startswith("i don't know") or t.startswith("i do not know")


def percentile(values, p):
    s = sorted(values)
    if not s:
        return 0.0
    k = (len(s) - 1) * p / 100
    lo, hi = int(k), min(int(k) + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def paths(version):
    return {"answers": RESULTS / f"answers_{version}.jsonl", "meta": RESULTS / f"answers_{version}.meta.json",
            "judged": RESULTS / f"judged_{version}.jsonl", "summary": RESULTS / f"generation_{version}.json",
            "md": RESULTS / f"generation_{version}.md"}


def load_questions(limit=None):
    rows = read_jsonl(EVAL_FILE)
    return rows[:limit] if limit else rows


# ====================================================================== rate limits
def rate_limit_wait(err):
    """How long to wait after a Groq RateLimitError, or None if it's the DAILY limit (waiting won't help)."""
    msg = str(err)
    if "per day" in msg or "TPD" in msg or "RPD" in msg or "insufficient_quota" in msg or "exceeded your current quota" in msg:
        return None                             # Groq daily limit / OpenAI quota: waiting a minute won't help
    m = re.search(r"try again in (?:(\d+)m)?([\d.]+)s", msg)
    if m:
        return int(m.group(1) or 0) * 60 + float(m.group(2)) + 1
    try:
        return float(err.response.headers.get("retry-after")) + 1
    except Exception:
        return 20


def is_rate_limit(err):
    return type(err).__name__ == "RateLimitError" or "rate limit" in str(err).lower() or "429" in str(err)


class DailyLimit(Exception):
    pass


def with_retries(fn, what, tries=6):
    for attempt in range(tries):
        try:
            return fn()
        except Exception as e:
            name, msg = type(e).__name__, str(e)
            if name in ("AuthenticationError", "PermissionDeniedError", "NotFoundError") or \
                    any(s in msg for s in ("Error code: 401", "Error code: 403", "Error code: 404",
                                           "invalid_api_key", "model_not_found")):
                sys.exit(f"\n[{what}] {msg[:300]}\n-> Retrying won't help: check the API key in .env "
                         f"(401) or the model name / access (403, 404). Nothing was saved for this question.")
            if not is_rate_limit(e):
                if attempt == tries - 1:
                    raise
                print(f"  [{what}] error: {e} -> retry in 5s")
                time.sleep(5)
                continue
            wait = rate_limit_wait(e)
            if wait is None:
                raise DailyLimit(str(e))
            print(f"  [{what}] rate limited -> waiting {wait:.0f}s")
            time.sleep(wait)
    raise RuntimeError(f"{what}: still failing after {tries} tries")


# ====================================================================== phase 1: answers
class Tee(io.StringIO):
    """Keeps a copy of what the pipeline prints while still showing it on screen."""
    def __init__(self, screen):
        super().__init__(); self.screen = screen

    def write(self, s):
        self.screen.write(s); return super().write(s)

def apply_settings(p, sets):
    for s in sets:
        name, _, raw = s.partition("=")
        name = name.strip()
        if not hasattr(p, name):
            sys.exit(f"--set {name}: src/pipeline.py has no setting called {name}. "
                     f"Get the final version of pipeline.py from Khadija first.")
        try:
            value = ast.literal_eval(raw)
        except Exception:
            value = raw                         # plain text, e.g. --set REWRITE_EFFORT=low
        setattr(p, name, value)
        print(f"setting {name} = {value!r}")
    return {k: getattr(p, k) for k in SETTINGS if hasattr(p, k)}


def run_answers(args):
    import src.pipeline as p
    P = paths(args.version)
    RESULTS.mkdir(parents=True, exist_ok=True)
    settings = apply_settings(p, args.set or [])

    meta = {"version": args.version, "settings": settings, "eval_file": str(EVAL_FILE.relative_to(ROOT))}
    if P["meta"].exists():
        old = json.loads(P["meta"].read_text(encoding="utf-8"))
        if old.get("settings") != settings:
            sys.exit(f"{P['answers'].name} was started with different settings:\n  {old.get('settings')}\n"
                     f"now:\n  {settings}\nUse another --version name, or delete the old files.")
    P["meta"].write_text(json.dumps(meta, indent=1), encoding="utf-8")

    done = {r["question"] for r in read_jsonl(P["answers"])}
    todo = [q for q in load_questions(args.limit) if q["question"] not in done]
    print(f"{args.version}: {len(done)} already answered, {len(todo)} to go. Settings: {settings}")
    if todo:
        print("warming up (loading models)...")
        p.get_reranker()
        p.retrieve("warm up", k=1)

    for i, q in enumerate(todo, 1):
        try:
            for attempt in range(3):
                # rewrite() hides its own errors: it prints "[rewrite] failed ..." and falls back to the raw
                # question. A rate-limited rewrite would silently lower the score, so catch that message.
                buf = Tee(sys.stdout)

                def timed():                    # time only the successful call, not rate-limit waits
                    t = time.perf_counter()
                    res = p.answer(q["question"])
                    return res, time.perf_counter() - t
                with contextlib.redirect_stdout(buf):
                    r, seconds = with_retries(timed, "answer")
                out = buf.getvalue()
                rewrite_failed = bool((r.get("rewrite") or {}).get("failed")) or \
                    "[rewrite] failed" in out or "[rewrite] using the original question" in out
                if not rewrite_failed:
                    break
                if any(s in buf.getvalue() for s in ("per day", "TPD", "insufficient_quota", "current quota")):
                    raise DailyLimit("rewrite model: " + buf.getvalue().strip()[:200])
                print(f"  rewrite failed -> waiting 30s and asking again")
                time.sleep(30)
        except DailyLimit as e:
            print(f"\nDAILY TOKEN LIMIT reached ({e}).\nSaved so far: {P['answers']}. "
                  f"Run the same command again tomorrow or with another key: it continues where it stopped.")
            return
        row = {"question": q["question"], "reference": q["answer"], "answerable": q["answerable"],
               "source_url": q.get("source_url", ""),
               "answer": r["answer"], "idk": is_idk(r["answer"]), "idk_reason": r.get("idk_reason"),
               "citations": r.get("citations", []),
               "chunks": [{k: c.get(k) for k in ("id", "title", "section", "url", "text", "score", "rerank_score")}
                          for c in r.get("chunks", [])],
               "rewrite": r.get("rewrite"), "rewrite_failed": rewrite_failed, "top_score": r.get("top_score"),
               "usage": r.get("usage"), "timings": r.get("timings"), "seconds": round(seconds, 3)}
        append_jsonl(P["answers"], row)
        flag = "IDK " if row["idk"] else "    "
        print(f"{len(done) + i:3}. {seconds:5.1f}s {flag}{'!rewrite ' if rewrite_failed else ''}{q['question'][:70]}")
        time.sleep(args.sleep)
    print(f"\nDone: {P['answers']}\nNext: py -m eval.generation_eval judge --version {args.version}")


# ====================================================================== phase 2: judge
CITE = re.compile(r"\[(\d+)\]")


MARKER = re.compile(r"[\s*_\-•]*(\d{1,2}|[a-zA-Z])[.)][\s*_]*|[\s*_\-•]+")


def is_marker(text):
    """True for a bare list number / bullet such as "1.", "**2.**", "a)", "-"."""
    return bool(MARKER.fullmatch(text.strip()))


def split_claims(answer):
    """Split an answer into sentences / list items, each with the [n] numbers it cites.
    A citation written after the full stop ("... 4.5:1. [1]") is moved back to its sentence."""
    parts = []
    for line in answer.splitlines():
        line = line.strip()
        if not line:
            continue
        pieces = [s for s in re.split(r"(?<=[.!?])\s+(?=[\[A-Z*\-•\d(\"'])", line) if s.strip()]
        merged = []
        for s in pieces:                                   # "1." / "a)" alone is a list number, not a claim:
            if merged and is_marker(merged[-1]):           # glue it to the text that follows
                merged[-1] = merged[-1] + " " + s
            else:
                merged.append(s)
        parts += [s for s in merged if not is_marker(s)]
    claims = []
    for s in parts:
        lead = re.match(r"^((?:\s*\[\d+\])+)\s*(.*)$", s)
        if lead and claims:                                # "[1] Next sentence" -> [1] belongs to the previous one
            claims[-1]["cites"] += [int(n) for n in CITE.findall(lead.group(1))]
            s = lead.group(2)
            if not s.strip():
                continue
        claims.append({"text": s.strip(), "cites": [int(n) for n in CITE.findall(s)]})
    for c in claims:
        c["cites"] = list(dict.fromkeys(c["cites"]))
    return claims


JUDGE_SYSTEM = """You are a strict, careful grader for a question-answering system about WCAG 2.2.
You get: a question, a reference answer written by a human, the system's answer split into numbered claims,
and the source passages that the claims cite. Judge ONLY from what is written; do not use outside knowledge
to decide whether a claim is supported.

Reply with ONLY one JSON object, no other text:
{"correctness": "correct" | "partial" | "incorrect",
 "correctness_reason": "<one short sentence>",
 "claims": [{"i": <claim number>, "factual": true|false, "supported": true|false,
             "citations": {"<n>": true|false}}]}

correctness (compare with the REFERENCE answer; skip it -> "n/a" if the reference is missing):
- "correct": the answer gives the key fact(s) of the reference. Extra correct detail or different wording is fine.
- "partial": some key facts are right but an important one is missing or vague.
- "incorrect": it contradicts the reference, gives a wrong value/level/success criterion, or misses the point.

claims (one entry for EVERY claim, same numbers):
- factual: false only for text with no checkable content (e.g. "Here is what WCAG says:", a heading).
- supported: true only if the passages cited BY THIS CLAIM state it (paraphrase is fine; an exemption,
  a level, or a number that the passages do not state for this case = false). A factual claim that cites
  nothing is "supported": false.
- citations: for each [n] the claim cites, true if passage n really supports what this claim says."""


def judge_prompt(row):
    claims = split_claims(row["answer"])
    cited = sorted({n for c in claims for n in c["cites"]})
    lines = [f"QUESTION: {row['question']}",
             f"REFERENCE ANSWER: {row['reference'] if row['answerable'] else '(none: the question is out of scope)'}",
             "", "SYSTEM ANSWER, split into claims:"]
    for i, c in enumerate(claims, 1):
        lines.append(f"{i}. {c['text']}   [cites: {', '.join(map(str, c['cites'])) or 'none'}]")
    lines += ["", "CITED SOURCE PASSAGES:"]
    for n in cited:
        if 1 <= n <= len(row["chunks"]):
            ch = row["chunks"][n - 1]
            lines.append(f"[{n}] {ch.get('title', '')} - {ch.get('section', '')}\n{ch.get('text', '')}\n")
        else:
            lines.append(f"[{n}] (this number does not exist: only {len(row['chunks'])} passages were given)\n")
    return "\n".join(lines), claims


def judge_provider(model):
    """Groq model names contain a slash ("openai/gpt-oss-20b"); OpenAI names don't ("gpt-5")."""
    return "groq" if "/" in model or model.startswith(("llama", "qwen", "gemma")) else "openai"


def get_judge_client(model):
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    if judge_provider(model) == "groq":
        from groq import Groq
        key = os.getenv("GROQ_JUDGE_API_KEY") or os.getenv("GROQ_API_KEY")
        if not key:
            sys.exit("No GROQ_JUDGE_API_KEY or GROQ_API_KEY in .env")
        return Groq(api_key=key)
    from openai import OpenAI
    key = os.getenv("OPENAI_JUDGE_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not key:
        sys.exit("No OPENAI_JUDGE_API_KEY or OPENAI_API_KEY in .env")
    return OpenAI(api_key=key)


def is_reasoning_model(model):
    """gpt-oss / gpt-5 / o-series 'think' first: they take reasoning_effort, and OpenAI's ones refuse temperature=0."""
    name = model.split("/")[-1]
    return name.startswith(("gpt-oss", "gpt-5", "gpt-6", "o1", "o3", "o4"))


def call_judge(client, model, prompt):
    kwargs = dict(model=model,
                  messages=[{"role": "system", "content": JUDGE_SYSTEM}, {"role": "user", "content": prompt}])
    if is_reasoning_model(model):
        kwargs["reasoning_effort"] = "low"     # judging is easy; saves most of the reasoning tokens
        if judge_provider(model) == "groq":
            kwargs["temperature"] = 0
    else:
        kwargs["temperature"] = 0
    try:
        resp = client.chat.completions.create(**kwargs)
    except Exception as e:                      # a model that refuses one of these options -> ask without it
        bad = [k for k in ("temperature", "reasoning_effort") if k in str(e) and k in kwargs]
        if not bad or is_rate_limit(e):
            raise
        for k in bad:
            kwargs.pop(k)
        resp = client.chat.completions.create(**kwargs)
    raw = resp.choices[0].message.content or ""
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        raise ValueError(f"judge returned no JSON: {raw[:200]}")
    u = getattr(resp, "usage", None)
    return json.loads(m.group(0)), (u.total_tokens if u else 0)


def judge_row(client, model, row):
    """Grades one saved answer. Refusals need no LLM call."""
    out = {"question": row["question"], "answerable": row["answerable"], "idk": row["idk"],
           "idk_correct": row["idk"] != row["answerable"], "judge_model": model}
    if row["idk"]:
        out.update(correctness="refused" if row["answerable"] else "n/a", claims=[], tokens=0)
        return out
    prompt, claims = judge_prompt(row)
    verdict, tokens = with_retries(lambda: call_judge(client, model, prompt), "judge")
    by_i = {int(c.get("i", 0)): c for c in verdict.get("claims", []) if str(c.get("i", "")).isdigit()}
    graded = []
    for i, c in enumerate(claims, 1):
        v = by_i.get(i, {})
        cit = {int(n): bool(ok) for n, ok in (v.get("citations") or {}).items() if str(n).isdigit()}
        for n in c["cites"]:
            if not 1 <= n <= len(row["chunks"]):
                cit[n] = False                  # citation to a passage that doesn't exist
            cit.setdefault(n, False)            # judge forgot it -> count as not verified
        factual = bool(v.get("factual", True))
        supported = bool(v.get("supported", False)) and bool(c["cites"])
        graded.append({"i": i, "text": c["text"], "cites": c["cites"], "factual": factual,
                       "supported": supported, "citations": {str(n): cit[n] for n in c["cites"]}})
    corr = verdict.get("correctness", "incorrect") if row["answerable"] else "n/a"
    if corr not in ("correct", "partial", "incorrect", "n/a"):
        corr = "incorrect"
    out.update(correctness=corr, correctness_reason=verdict.get("correctness_reason", ""),
               claims=graded, tokens=tokens)
    return out


def run_judge(args):
    P = paths(args.version)
    answers = read_jsonl(P["answers"])
    if not answers:
        sys.exit(f"No answers yet: run  py -m eval.generation_eval answer --version {args.version}")
    if args.limit:
        answers = answers[:args.limit]
    done = {r["question"] for r in read_jsonl(P["judged"])}
    todo = [a for a in answers if a["question"] not in done]
    print(f"judge {args.judge_model}: {len(done)} already judged, {len(todo)} to go")
    answer_model = (json.loads(P["meta"].read_text(encoding="utf-8")).get("settings", {}).get("MODEL", "")
                    if P["meta"].exists() else "")
    if answer_model and answer_model.split("/")[-1] == args.judge_model.split("/")[-1]:
        print(f"⚠️  The judge ({args.judge_model}) is the same model that wrote the answers: it may grade its own "
              f"answers too kindly. Use another one with --judge-model.")
    client = get_judge_client(args.judge_model) if any(not a["idk"] for a in todo) else None
    for i, row in enumerate(todo, 1):
        try:
            j = judge_row(client, args.judge_model, row)
        except DailyLimit as e:
            print(f"\nTOKEN LIMIT / QUOTA reached for the judge ({e}). Run again later, or put another key in "
                  f"OPENAI_JUDGE_API_KEY (or GROQ_JUDGE_API_KEY). Judged answers are saved.")
            break
        except Exception as e:
            print(f"  could not judge '{row['question'][:60]}': {e} (skipped; run again to retry)")
            continue
        append_jsonl(P["judged"], j)
        print(f"{len(done) + i:3}. {j['correctness']:9} {row['question'][:70]}")
        if not row["idk"]:
            time.sleep(args.sleep)
    summarise(args.version)


# ====================================================================== summary
def current_answers(P):
    """Saved answers, restricted to the questions that are in data/eval.jsonl NOW.
    So if questions are removed from the eval set later, old runs are re-scored on the same set
    without any new LLM call (run `summary` again)."""
    rows = read_jsonl(P["answers"])
    current = {q["question"] for q in read_jsonl(EVAL_FILE)}
    kept = [r for r in rows if not current or r["question"] in current]
    if len(kept) < len(rows):
        print(f"({len(rows) - len(kept)} saved answers ignored: those questions are no longer in {EVAL_FILE.name})")
    return {r["question"]: r for r in kept}


def summarise(version):
    P = paths(version)
    answers = current_answers(P)
    judged = [j for j in read_jsonl(P["judged"]) if j["question"] in answers]
    if not judged:
        print("nothing judged yet"); return None
    ans = [j for j in judged if j["answerable"]]
    una = [j for j in judged if not j["answerable"]]
    count = lambda xs, v: sum(j["correctness"] == v for j in xs)
    correct, partial = count(ans, "correct"), count(ans, "partial")
    idk_ok_una = sum(j["idk"] for j in una)
    n = len(judged)

    answered = [j for j in judged if not j["idk"]]
    per_answer, all_cits, uncited, fully = [], [], 0, 0
    for j in answered:
        # list numbers judged before the split_claims fix are ignored, so old judged files stay usable
        fact = [c for c in j["claims"] if c["factual"] and not is_marker(c["text"])]
        uncited += sum(1 for c in fact if not c["cites"])
        if fact:
            per_answer.append(sum(c["supported"] for c in fact) / len(fact))
            fully += all(c["supported"] for c in fact)
        all_cits += [ok for c in j["claims"] for ok in c["citations"].values()]

    rows = [answers[j["question"]] for j in judged]
    secs = [r["seconds"] for r in rows] or [0]
    settings = json.loads(P["meta"].read_text(encoding="utf-8"))["settings"] if P["meta"].exists() else {}
    cost = _avg_cost(rows, settings)
    s = {
        "version": version,
        "settings": settings,
        "n_questions": n, "n_answerable": len(ans), "n_unanswerable": len(una),
        "accuracy": (correct + idk_ok_una) / n,
        "accuracy_lenient": (correct + 0.5 * partial + idk_ok_una) / n,
        "correctness_answerable": {"correct": correct, "partial": partial,
                                   "incorrect": count(ans, "incorrect"), "refused": count(ans, "refused")},
        "correct_rate_answerable": correct / max(1, len(ans)),
        "idk_accuracy": sum(j["idk_correct"] for j in judged) / n,
        "false_idk": count(ans, "refused"),
        "false_idk_low_score": sum(answers[j["question"]].get("idk_reason") == "low_score"
                                   for j in ans if j["correctness"] == "refused"),
        "false_answer_unanswerable": len(una) - idk_ok_una,
        "faithfulness": statistics.mean(per_answer) if per_answer else None,
        "fully_faithful_answers": fully / max(1, len(per_answer)),
        "uncited_factual_claims": uncited,
        "citation_accuracy": sum(all_cits) / len(all_cits) if all_cits else None,
        "n_citations": len(all_cits),
        "answers_without_citation": sum(1 for j in answered if not any(c["cites"] for c in j["claims"])),
        "rewrite_failures": sum(r.get("rewrite_failed", False) for r in rows),
        "latency_p50_s": round(percentile(secs, 50), 2), "latency_p95_s": round(percentile(secs, 95), 2),
        "cost_per_request_usd": cost,
        "judge_tokens": sum(j.get("tokens", 0) for j in judged),
        "judge_model": next((j["judge_model"] for j in judged), JUDGE_MODEL),
    }
    examples = {
        "incorrect_or_partial": [{"q": j["question"], "verdict": j["correctness"], "why": j.get("correctness_reason", ""),
                                  "answer": answers[j["question"]]["answer"][:300],
                                  "reference": answers[j["question"]]["reference"][:200]}
                                 for j in ans if j["correctness"] in ("incorrect", "partial")],
        "false_idk": [{"q": j["question"], "reason": answers[j["question"]].get("idk_reason"),
                       "top_score": answers[j["question"]].get("top_score")}
                      for j in ans if j["correctness"] == "refused"],
        "answered_out_of_scope": [{"q": j["question"], "answer": answers[j["question"]]["answer"][:300]}
                                  for j in una if not j["idk"]],
        "unsupported_claims": [{"q": j["question"], "claim": c["text"], "cites": c["cites"]}
                               for j in answered for c in j["claims"] if c["factual"] and not c["supported"]],
    }
    json.dump({"summary": s, "examples": examples}, open(P["summary"], "w", encoding="utf-8"),
              indent=1, ensure_ascii=False)
    md = summary_md(s, examples)
    P["md"].write_text(md, encoding="utf-8")
    print("\n" + md + f"\nSaved {P['summary'].name} and {P['md'].name} in eval/results/")
    return s


def load_prices():
    """Read the PRICES table {model: (input $/1M, output $/1M)} from eval/latency_cost.py WITHOUT importing it
    (importing it would load the whole pipeline). Returns {} if it can't be read."""
    try:
        tree = ast.parse((ROOT / "eval" / "latency_cost.py").read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, ast.Assign) and any(getattr(t, "id", "") == "PRICES" for t in node.targets):
                return ast.literal_eval(node.value)
    except Exception:
        pass
    return {}


def _avg_cost(rows, settings):
    """Average cost per request, with the prices of the models this run actually used (from its settings)."""
    prices = load_prices()
    answer_model, rewrite_model = settings.get("MODEL"), settings.get("REWRITE_MODEL")
    if answer_model not in prices or rewrite_model not in prices:
        print(f"⚠️  no price for {answer_model} / {rewrite_model} in PRICES (eval/latency_cost.py) -> cost shown as n/a")
        return None
    (a_in, a_out), (r_in, r_out) = prices[answer_model], prices[rewrite_model]
    costs = []
    for r in rows:
        u = r.get("usage") or {}
        costs.append(u.get("prompt", 0) / 1e6 * a_in + u.get("completion", 0) / 1e6 * a_out
                     + u.get("rewrite_prompt", 0) / 1e6 * r_in + u.get("rewrite_completion", 0) / 1e6 * r_out)
    return round(sum(costs) / max(1, len(costs)), 6)


def money(x):
    return "n/a" if x is None else f"${x:.6f}"


def pct(x):
    return "n/a" if x is None else f"{100 * x:.1f}%"


def summary_md(s, ex):
    c = s["correctness_answerable"]
    out = [f"## Generation eval: `{s['version']}`", "",
           f"Settings: `{json.dumps(s['settings'])}` · judge: {s['judge_model']}", "",
           "| Metric | Value |", "|---|---|",
           f"| **Accuracy** (correct answers + correct \"I don't know\", all {s['n_questions']} questions) | **{pct(s['accuracy'])}** |",
           f"| Accuracy, partial = 0.5 | {pct(s['accuracy_lenient'])} |",
           f"| Correct on answerable ({s['n_answerable']}) | {pct(s['correct_rate_answerable'])} "
           f"(correct {c['correct']} · partial {c['partial']} · incorrect {c['incorrect']} · refused {c['refused']}) |",
           f"| \"I don't know\" accuracy | {pct(s['idk_accuracy'])} |",
           f"| False \"I don't know\" (answerable refused) | {s['false_idk']} ({s['false_idk_low_score']} by the score threshold) |",
           f"| Out-of-scope questions answered anyway | {s['false_answer_unanswerable']} / {s['n_unanswerable']} |",
           f"| Faithfulness (claims supported by their cited chunks) | {pct(s['faithfulness'])} |",
           f"| Fully faithful answers | {pct(s['fully_faithful_answers'])} |",
           f"| Citation accuracy ({s['n_citations']} citations) | {pct(s['citation_accuracy'])} |",
           f"| Factual claims with no citation | {s['uncited_factual_claims']} |",
           f"| Latency p50 / p95 (end to end, all questions) | {s['latency_p50_s']} s / {s['latency_p95_s']} s |",
           f"| Cost per request | {money(s['cost_per_request_usd'])} |"]
    if s["rewrite_failures"]:
        out.append(f"| ⚠️ Rewrite failures (rate limit?) | {s['rewrite_failures']} |")
    out += ["", "### Wrong or incomplete answers"]
    out += [f"- **{e['verdict']}**: {e['q']}: {e['why']}" for e in ex["incorrect_or_partial"][:12]] or ["- none"]
    out += ["", "### False \"I don't know\""]
    out += [f"- {e['q']} ({e['reason']}, top score {e['top_score'] if e['top_score'] is None else round(e['top_score'], 2)})"
            for e in ex["false_idk"][:12]] or ["- none"]
    out += ["", "### Unsupported claims (faithfulness failures)"]
    out += [f"- {e['q']} → \"{e['claim'][:160]}\" cites {e['cites'] or 'nothing'}"
            for e in ex["unsupported_claims"][:12]] or ["- none"]
    if ex["answered_out_of_scope"]:
        out += ["", "### Out-of-scope questions answered anyway"]
        out += [f"- {e['q']} → {e['answer'][:150]}" for e in ex["answered_out_of_scope"]]
    return "\n".join(out) + "\n"


# ====================================================================== compare + threshold
def run_compare(args):
    a, b = (json.load(open(paths(v)["summary"], encoding="utf-8"))["summary"] for v in (args.before, args.after))
    if a["n_questions"] != b["n_questions"]:
        print(f"⚠️ not the same number of questions ({a['n_questions']} vs {b['n_questions']}): finish both runs first.")
    pts = lambda k: (b[k] - a[k]) * 100 if a.get(k) is not None and b.get(k) is not None else None
    rel = lambda k: (b[k] - a[k]) / a[k] * 100 if a.get(k) else None
    rows = [("**Accuracy**", pct(a["accuracy"]), pct(b["accuracy"]), f"{pts('accuracy'):+.1f} pts"),
            ("Accuracy (partial = 0.5)", pct(a["accuracy_lenient"]), pct(b["accuracy_lenient"]), f"{pts('accuracy_lenient'):+.1f} pts"),
            ("\"I don't know\" accuracy", pct(a["idk_accuracy"]), pct(b["idk_accuracy"]), f"{pts('idk_accuracy'):+.1f} pts"),
            ("Faithfulness", pct(a["faithfulness"]), pct(b["faithfulness"]),
             "n/a" if pts("faithfulness") is None else f"{pts('faithfulness'):+.1f} pts"),
            ("Citation accuracy", pct(a["citation_accuracy"]), pct(b["citation_accuracy"]),
             "n/a" if pts("citation_accuracy") is None else f"{pts('citation_accuracy'):+.1f} pts"),
            ("Latency p50", f"{a['latency_p50_s']} s", f"{b['latency_p50_s']} s", f"{rel('latency_p50_s') or 0:+.0f}%"),
            ("Latency p95", f"{a['latency_p95_s']} s", f"{b['latency_p95_s']} s", f"{rel('latency_p95_s') or 0:+.0f}%"),
            ("Cost / request", money(a["cost_per_request_usd"]), money(b["cost_per_request_usd"]),
             "n/a" if rel("cost_per_request_usd") is None else f"{rel('cost_per_request_usd'):+.0f}%")]
    drop = -pts("accuracy")
    verdict = (f"✅ Accuracy {'drop' if drop > 0 else 'change'}: {abs(drop):.1f} points → within the 2-point rule."
               if drop <= 2 else f"❌ Accuracy dropped {drop:.1f} points → breaks the 2-point rule.")
    cut = max(-(rel("cost_per_request_usd") or 0), -(rel("latency_p95_s") or 0))
    target = "✅ reaches" if cut >= 50 else "❌ does not reach"
    md = "\n".join([f"| Metric | {args.before} | {args.after} | Change |", "|---|---|---|---|",
                    *[f"| {r[0]} | {r[1]} | {r[2]} | {r[3]} |" for r in rows], "",
                    f"{a['n_questions']} questions, same eval set and judge ({a['judge_model']}).", "",
                    verdict, f"Best cut in cost or p95: {cut:.0f}% → {target} the 50% target."])
    out = RESULTS / f"compare_{args.before}_vs_{args.after}.md"
    out.write_text(md + "\n", encoding="utf-8")
    print(md + f"\n\nSaved {out} → paste it into docs/optimisation.md §4")


def run_threshold(args):
    """What if MIN_SCORE were higher? Uses saved top_score + judge verdicts, no new LLM calls.
    Only thresholds >= the one used in the run can be simulated (below it we never saw the LLM's answer)."""
    P = paths(args.version)
    answers = current_answers(P)
    judged = {j["question"]: j for j in read_jsonl(P["judged"])}
    rows = [(answers[q], judged[q]) for q in judged if q in answers]
    if not rows:
        sys.exit("judge the run first")
    base = json.loads(P["meta"].read_text(encoding="utf-8"))["settings"].get("MIN_SCORE", 0.0)
    n, n_una = len(rows), sum(not a["answerable"] for a, _ in rows)
    lines = ["| MIN_SCORE | accuracy | IDK accuracy | answerable refused | out-of-scope answered | answer-LLM calls saved |",
             "|---|---|---|---|---|---|"]
    table = []
    for t in [base + d / 2 for d in range(0, 13)]:          # base, base+0.5, ... base+6
        acc = idk_ok = refused = wrong_ans = saved = 0
        for a, j in rows:
            score = a.get("top_score")
            idk = a["idk"] or score is None or score < t
            # the answer LLM was called in the run (not a low_score refusal) but would now be skipped
            saved += a.get("idk_reason") != "low_score" and score is not None and score < t
            if a["answerable"]:
                acc += (not idk) and j["correctness"] == "correct"
                refused += idk
                idk_ok += not idk
            else:
                acc += idk; idk_ok += idk; wrong_ans += not idk
        table.append((t, acc, saved))
        lines.append(f"| {t:g} | {100 * acc / n:.1f}% | {100 * idk_ok / n:.1f}% | {refused} | {wrong_ans} / {n_una} | {saved} |")
    best_acc = max(acc for _, acc, _ in table)
    # recommendation: best accuracy; among ties, the one that saves the most answer calls, then the lowest threshold
    best = sorted([r for r in table if r[1] == best_acc], key=lambda r: (-r[2], r[0]))[0]
    lines += ["", f"{n} questions ({n_una} out of scope). Thresholds below {base:g} can't be simulated "
                  f"(the run never asked the LLM for those questions).",
              f"Recommended MIN_SCORE = {best[0]:g}: highest accuracy ({100 * best_acc / n:.1f}%), "
              f"saves {best[2]} answer-LLM calls on this set.",
              "With few out-of-scope questions, prefer the lowest threshold that reaches this accuracy if you are unsure."]
    md = "\n".join(lines)
    out = RESULTS / f"threshold_{args.version}.md"
    out.write_text(md + "\n", encoding="utf-8")
    print(md + f"\n\nSaved {out} -> send the recommended value to Khadija")


def run_show(args):
    """Print judged answers one by one, to check the judge by hand (no LLM calls)."""
    P = paths(args.version)
    answers = {r["question"]: r for r in read_jsonl(P["answers"])}
    judged = [j for j in read_jsonl(P["judged"]) if j["question"] in answers]
    if args.only:
        judged = [j for j in judged if j["correctness"] == args.only]
    for i, j in enumerate(judged[:args.n], 1):
        a = answers[j["question"]]
        print("=" * 80)
        print(f"#{i}  JUDGE: {j['correctness'].upper()}   {j.get('correctness_reason', '')}")
        print(f"Q:   {j['question']}")
        print(f"REF: {a['reference']}")
        print(f"ANSWER:\n{a['answer']}")
        for c in j["claims"]:
            if is_marker(c["text"]):
                continue
            mark = "ok " if c["supported"] else ("-- " if not c["factual"] else "NO ")
            print(f"   [{mark}] {c['text'][:110]}  cites {c['cites'] or 'nothing'}")
    print("=" * 80)
    print("ok = supported by its cited chunk · NO = unsupported · -- = not a factual claim")
    print("Write down for each one: do you agree with the judge? (yes / no)")


# ====================================================================== CLI
def main():
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")                 # so JUDGE_MODEL=... in .env works
    default_judge = os.getenv("JUDGE_MODEL") or JUDGE_MODEL
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("answer", "judge", "threshold", "summary"):
        sp = sub.add_parser(name)
        sp.add_argument("--version", default="baseline")
        sp.add_argument("--limit", type=int)
        sp.add_argument("--sleep", type=float, default=1.0)
        sp.add_argument("--judge-model", default=default_judge)
        if name == "answer":
            sp.add_argument("--set", action="append", metavar="NAME=VALUE",
                            help="change a src/pipeline.py setting, e.g. --set TOP_K=3")
    cp = sub.add_parser("compare"); cp.add_argument("before"); cp.add_argument("after")
    sh = sub.add_parser("show")
    sh.add_argument("--version", default="baseline")
    sh.add_argument("--n", type=int, default=10)
    sh.add_argument("--only", choices=["correct", "partial", "incorrect", "refused", "n/a"])
    args = ap.parse_args()
    {"answer": run_answers, "judge": run_judge, "compare": run_compare, "threshold": run_threshold,
     "summary": lambda a: summarise(a.version), "show": run_show}[args.cmd](args)


if __name__ == "__main__":
    sys.stdout.reconfigure(errors="replace")
    main()
