"""Draft eval questions from the corpus. Needs GROQ_API_KEY in .env (your own key, never commit it).
Run from the project folder:  python eval/make_questions.py [--n 100] [--seed 1] [--out data/eval_draft.jsonl]
The output is a DRAFT: a human must review every line before it becomes data/eval.jsonl.
Each answerable row follows data/FORMATS.md: question, answer, source_url, source_passage, answerable."""
import json, os, re, sys, time, random, collections, pathlib
import requests
from dotenv import load_dotenv
load_dotenv()

API = "https://api.groq.com/openai/v1/chat/completions"
SKIP_SECTIONS = {"key terms", "related resources", "help with using these understanding documents", "references", "acknowledgements"}
QUOTA = {"understanding": 0.45, "techniques": 0.35}   # the rest comes from the spec page

UNANSWERABLE = [
    "What is the capital of France?", "How do I center a div with CSS flexbox?",
    "What does GDPR say about cookie consent banners?", "Which screen reader has the largest market share?",
    "How do I install NVDA on Windows?", "What is the best colour palette for a bank website?",
    "How do I make a React app load faster?", "Who won the 2022 football World Cup?",
    "How much does an accessibility audit cost?", "What is the penalty for violating the European Accessibility Act?",
    "Which JavaScript framework is best for accessible apps?", "How do I write a unit test in Python?",
]

PROMPT = """You are helping build a test set for a chatbot that answers web developers' questions about WCAG 2.2.
Read the passage and write ONE question a developer might realistically ask that can be answered using ONLY this passage.
Rules:
- Do NOT copy the passage's wording. Never say "the passage", "this document" or "this page".
- The question must make sense on its own (name the topic, success criterion or technique if needed).
- The answer must be short (max 40 words) and factual.
- "evidence" = 1-2 sentences copied EXACTLY from the passage that support the answer.
Return ONLY JSON: {{"question": "...", "answer": "...", "evidence": "..."}}

Page title: {title}
Section: {section}
Passage:
{body}"""

def arg(name, default, cast=str):
    return cast(sys.argv[sys.argv.index(name) + 1]) if name in sys.argv else default

def norm(s): return re.sub(r"\W+", " ", s.lower()).strip()
def body(c): return c["text"].split("\n", 1)[-1]
def kind(url): return "understanding" if "/Understanding/" in url else "techniques" if "/Techniques/" in url else "spec"

def llm(prompt):
    key = os.getenv("GROQ_API_KEY")
    if not key: sys.exit("Set GROQ_API_KEY in your .env file first.")
    payload = {"model": os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"), "temperature": 0.3, "max_tokens": 2000,
               "reasoning_effort": "low", "messages": [{"role": "user", "content": prompt}]}
    for attempt in range(8):
        try:
            r = requests.post(API, headers={"Authorization": f"Bearer {key}"}, json=payload, timeout=90)
        except requests.RequestException as e:   # internet blip: wait and retry
            print("  network problem, retrying...", type(e).__name__); time.sleep(5 * (attempt + 1)); continue
        if r.status_code == 429 or r.status_code >= 500: time.sleep(5 * (attempt + 1)); continue
        if r.status_code == 400 and "reasoning" in r.text.lower(): payload.pop("reasoning_effort", None); continue
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"] or ""
    raise RuntimeError("Groq did not answer (rate limit or no internet). Run the same command again with --resume.")

def parse(text):
    m = re.search(r"\{.*\}", text, re.S)
    if not m: return None
    try: d = json.loads(m.group(0))
    except Exception: return None
    return d if all(isinstance(d.get(k), str) and d[k].strip() for k in ("question", "answer", "evidence")) else None

def main():
    n, seed, out = arg("--n", 100, int), arg("--seed", 1, int), arg("--out", "data/eval_draft.jsonl")
    rng = random.Random(seed)
    chunks = [json.loads(l) for l in open("data/chunks.jsonl", encoding="utf-8")]
    by_url = collections.defaultdict(list)
    for c in chunks:
        if c["section"].strip().lower() not in SKIP_SECTIONS and len(body(c).split()) >= 60:
            by_url[c["url"]].append(c)
    pools = {"understanding": [], "techniques": [], "spec": []}
    for url, cs in by_url.items():
        if kind(url) == "spec": pools["spec"] += cs
        else: pools[kind(url)].append(rng.choice(cs))   # at most one question per page
    quota = {k: round(n * q) for k, q in QUOTA.items()}; quota["spec"] = n - sum(quota.values())
    partial = pathlib.Path(out + ".partial")
    rows = []
    if "--resume" in sys.argv and partial.exists():
        rows = [json.loads(l) for l in open(partial, encoding="utf-8") if l.strip()]
        print("resuming: already have", len(rows), "questions")
    done = {r["_cid"] for r in rows}
    pf = open(partial, "a" if rows else "w", encoding="utf-8")
    tried, stop = 0, False
    quota = {k: round(n * q) for k, q in QUOTA.items()}; quota["spec"] = n - sum(quota.values())
    for k, pool in pools.items():
        if stop: break
        rng.shuffle(pool); got = sum(1 for r in rows if kind(r["source_url"]) == k)
        for c in pool:
            if got >= quota[k]: break
            if c["id"] in done: continue
            tried += 1
            try:
                d = parse(llm(PROMPT.format(title=c["title"], section=c["section"], body=body(c))))
            except (RuntimeError, KeyboardInterrupt) as e:   # keep what we already have
                print("\nSTOPPED EARLY:", e or "interrupted"); stop = True; break
            if not d or norm(d["evidence"]) not in norm(body(c)):   # drop hallucinated evidence
                print("  skipped (bad output)", c["url"].split("/")[-1]); continue
            row = {"question": d["question"].strip(), "answer": d["answer"].strip(), "source_url": c["url"],
                   "source_passage": d["evidence"].strip(), "answerable": True, "_cid": c["id"]}
            rows.append(row); got += 1
            pf.write(json.dumps(row, ensure_ascii=False) + "\n"); pf.flush()   # saved after every question
            print(f"[{k}] {len(rows)}/{n}  {d['question'][:70]}")
            time.sleep(0.4)
    pf.close()
    final = [{a: b for a, b in r.items() if a != "_cid"} for r in rows]
    final += [{"question": q, "answer": "I don't know", "source_url": "", "source_passage": "", "answerable": False} for q in UNANSWERABLE]
    rng.shuffle(final)
    with open(out, "w", encoding="utf-8") as f:
        for r in final: f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"\nwrote {len(final)} draft rows ({len(rows)} answerable) -> {out}")
    if stop: print("Not finished. Run the same command again with --resume to continue where it stopped.")
    else: partial.unlink(missing_ok=True)

if __name__ == "__main__":
    main()
