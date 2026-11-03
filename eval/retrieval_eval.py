"""MAYA - T1. Retrieval eval: recall@k on the answerable questions of data/eval.jsonl.

A HIT = one of the top-k retrieved chunks contains the gold source_passage (or most of it).
We do NOT count a hit just because the URL matches: https://www.w3.org/TR/WCAG22 is the whole spec
(184 chunks), so URL matching "succeeds" almost always. The URL-only number is still printed, labelled,
so the report can show the difference.

Passage match (both sides normalised: lower case, same quotes/dashes, one space between words):
  1. the passage is a substring of the chunk text, or
  2. the longest run of consecutive passage words found in the chunk covers >= 60% of the passage
     (covers passages that the chunker cut in two: the chunk holding most of it counts), or
  3. >= 85% of the passage's words appear in the chunk in the same order (covers small edits).
  A looser "60% of the words in order" rule was tested and rejected: boilerplate such as
  "This technique relates to 1.4.4 Resize Text ( Advisory )" then matched the wrong pages.
  If a gold passage is boilerplate (found on more than 3 pages), only chunks from its source_url count.
The gold chunk ids are computed ONCE per question over the whole corpus (gold_sets), so every system is
scored against exactly the same targets.

Run from the project root:
    py -m eval.retrieval_eval                 # bm25, vector, hybrid  (k = 1, 3, 5, 10)
    py -m eval.retrieval_eval --modes hybrid  # one mode only
Writes eval/results/retrieval.json and eval/results/retrieval.md
"""
import argparse
import difflib
import json
import re
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

KS = [1, 3, 5, 10]
RUN = 0.60              # longest consecutive run of passage words found in the chunk, as a share of the passage
OVERLAP = 0.85          # share of the passage's words found in the same order (allows small edits)
RESULTS = ROOT / "eval" / "results"


# ---------------------------------------------------------------- normalising
_QUOTES = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"',
                         "–": "-", "—": "-", " ": " ", "​": ""})


def norm_text(s):
    return re.sub(r"\s+", " ", (s or "").translate(_QUOTES).lower()).strip()


def words(s):
    return re.findall(r"\w+", norm_text(s))


def norm_url(u):
    """Same rule as eval/review_tool.py: strip .html and the trailing slash."""
    return re.sub(r"\.html$", "", (u or "").strip()).rstrip("/")


# ---------------------------------------------------------------- matching
def overlap(passage_words, chunk_words):
    """(longest run, ordered overlap) of the passage's words in the chunk, both as a share 0..1."""
    if not passage_words:
        return 0.0, 0.0
    blocks = difflib.SequenceMatcher(None, passage_words, chunk_words, autojunk=False).get_matching_blocks()
    n = len(passage_words)
    return max(b.size for b in blocks) / n, sum(b.size for b in blocks) / n


def _hit(p, pw, t, w, ws):
    """p/pw = normalised passage text/words; t/w/ws = normalised chunk text/words/word set."""
    if p and p in t:
        return True
    # quick filter before the slower ordered match: enough shared words at all?
    if not pw or len(set(pw) & ws) < RUN * len(set(pw)):
        return False
    run, ordered = overlap(pw, w)
    return run >= RUN or ordered >= OVERLAP


def passage_hit(passage, chunk_text):
    """Does this chunk contain the gold passage (or most of it)?"""
    w = words(chunk_text)
    return _hit(norm_text(passage), words(passage), norm_text(chunk_text), w, set(w))


# ---------------------------------------------------------------- data
def load_eval(path=ROOT / "data" / "eval.jsonl"):
    rows = [json.loads(l) for l in open(path, encoding="utf-8-sig") if l.strip()]
    return [r for r in rows if r.get("answerable", True) and r.get("source_passage", "").strip()]


def load_chunks(path=ROOT / "data" / "chunks.jsonl"):
    return [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]


MAX_PAGES = 3   # a passage found on more pages than this is boilerplate -> only its own page counts


def gold_sets(rows, chunks):
    """For each question, the set of chunk ids that count as a hit (computed once over the whole corpus).
    - Normal passage: every chunk that contains it (the same SC text on the spec page and on the
      Understanding page are both right answers).
    - Boilerplate passage (found on > MAX_PAGES pages, e.g. "This technique relates to ..." or the
      "Key Terms" text W3C repeats at the bottom of many pages): only chunks from its source_url.
    An empty set means the passage is in no chunk at all -> a data problem, not a retrieval one."""
    pre = [(c, norm_text(c["text"]), words(c["text"])) for c in chunks]   # normalise each chunk once
    pre = [(c, t, w, set(w)) for c, t, w in pre]
    out = []
    for r in rows:
        p, pw = norm_text(r["source_passage"]), words(r["source_passage"])
        matching = [c for c, t, w, ws in pre if _hit(p, pw, t, w, ws)]
        pages = {norm_url(c["url"]) for c in matching}
        boilerplate = len(pages) > MAX_PAGES
        if boilerplate:
            matching = [c for c in matching if norm_url(c["url"]) == norm_url(r["source_url"])]
        out.append({"ids": {c["id"] for c in matching}, "pages": len(pages), "boilerplate": boilerplate})
    return out


# ---------------------------------------------------------------- evaluation
def percentile(values, p):
    s = sorted(values)
    if not s:
        return 0.0
    k = (len(s) - 1) * p / 100
    lo, hi = int(k), min(int(k) + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def evaluate(search, rows, gold, ks=KS, label=""):
    """search(question, k) -> list of chunk dicts (best first). gold = gold_sets(rows, chunks).
    Returns recall@k (passage match), URL-only recall@k, MRR, search latency, and the misses."""
    kmax = max(ks)
    hits = {k: 0 for k in ks}
    url_hits = {k: 0 for k in ks}
    times, misses, per_q = [], [], []
    for i, r in enumerate(rows):
        t = time.perf_counter()
        res = search(r["question"], kmax)
        times.append((time.perf_counter() - t) * 1000)
        if label and (i + 1) % 25 == 0:
            print(f"  {label}: {i + 1}/{len(rows)}", flush=True)

        first = next((j + 1 for j, c in enumerate(res[:kmax]) if c["id"] in gold[i]["ids"]), None)
        gold_url = norm_url(r["source_url"])
        url_first = next((j + 1 for j, c in enumerate(res[:kmax]) if norm_url(c["url"]) == gold_url), None)
        for k in ks:
            hits[k] += first is not None and first <= k
            url_hits[k] += url_first is not None and url_first <= k
        per_q.append({"question": r["question"], "rank": first, "url_rank": url_first})
        if first is None or first > 5:
            misses.append({"question": r["question"], "gold_url": gold_url,
                           "passage": r["source_passage"][:160],
                           "in_corpus": bool(gold[i]["ids"]),
                           "got": [f"{c['id']} | {c.get('section', '')}" for c in res[:3]]})
    n = max(1, len(rows))
    rr = [1 / q["rank"] for q in per_q if q["rank"]]
    return {"n": len(rows),
            **{f"recall@{k}": hits[k] / n for k in ks},
            **{f"url_recall@{k}": url_hits[k] / n for k in ks},
            "mrr@10": sum(rr) / n,
            "ms_mean": statistics.mean(times) if times else 0.0,
            "ms_p50": percentile(times, 50), "ms_p95": percentile(times, 95),
            "misses": misses, "per_question": per_q}


def table(results, ks=KS):
    head = ("| System | " + " | ".join(f"R@{k}" for k in ks) + " | MRR@10 | URL-only R@5 | p50 ms | p95 ms |\n"
            "|---|" + "---|" * (len(ks) + 4))
    lines = [f"| {name} | " + " | ".join(f"{r[f'recall@{k}']:.2f}" for k in ks)
             + f" | {r['mrr@10']:.2f} | {r['url_recall@5']:.2f} | {r['ms_p50']:.0f} | {r['ms_p95']:.0f} |"
             for name, r in results.items()]
    return head + "\n" + "\n".join(lines)


def save(name, results, rows, gold, extra_note=""):
    RESULTS.mkdir(parents=True, exist_ok=True)
    n_cov = sum(bool(g["ids"]) for g in gold)
    n_boiler = sum(g["boilerplate"] for g in gold)
    note = (f"\n\n{len(rows)} answerable questions. R@k = a top-k chunk contains the gold passage "
            f"(substring, a run of >= {RUN:.0%} of its words, or >= {OVERLAP:.0%} of its words in order; "
            f"for the {n_boiler} boilerplate passages found on > {MAX_PAGES} pages, only chunks from the source page count). "
            f"URL-only R@5 = the gold page is in the top 5 (inflated: the whole WCAG 2.2 spec is one URL). "
            f"{n_cov}/{len(rows)} gold passages are in data/chunks.jsonl at all. "
            f"Latency = the search step only, models already loaded.{extra_note}")
    md = table(results) + note
    (RESULTS / f"{name}.md").write_text(md + "\n", encoding="utf-8")
    json.dump({"n_questions": len(rows), "gold_in_corpus": n_cov, "boilerplate_passages": n_boiler,
               "not_in_corpus": [r["question"] for r, g in zip(rows, gold) if not g["ids"]],
               "systems": results},
              open(RESULTS / f"{name}.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    return md


def prepare():
    """Load the eval rows and compute the gold chunk sets (shared with eval/ablation.py)."""
    rows, chunks = load_eval(), load_chunks()
    print(f"answerable eval questions: {len(rows)}")
    gold = gold_sets(rows, chunks)
    print(f"gold passage found in the corpus: {sum(bool(g['ids']) for g in gold)}/{len(rows)} "
          f"({sum(g['boilerplate'] for g in gold)} boilerplate passages -> source page only)")
    return rows, gold


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--modes", nargs="+", default=["bm25", "vector", "hybrid"])
    args = ap.parse_args()

    from src.retrieve import retrieve
    rows, gold = prepare()
    retrieve("warm up", k=1, mode="hybrid")      # load models first so loading isn't timed

    out = {}
    for mode in args.modes:
        out[mode] = evaluate(lambda q, k, m=mode: retrieve(q, k, m), rows, gold)
        r = out[mode]
        print(f"{mode:7} " + "  ".join(f"R@{k}={r[f'recall@{k}']:.3f}" for k in KS)
              + f"  | URL-only R@5={r['url_recall@5']:.3f} | {r['ms_p50']:.0f} ms p50, {r['ms_p95']:.0f} ms p95")

    print("\n" + save("retrieval", out, rows, gold))
    last = args.modes[-1]
    print(f"\n{last} misses at k=5 (first 15):")
    for m in out[last]["misses"][:15]:
        flag = "" if m["in_corpus"] else "  [passage NOT in any chunk]"
        print(f" - {m['question'][:85]}{flag}\n     gold: {m['gold_url'].split('/')[-1]} | got: {m['got'][0][:70]}")
    print(f"\nSaved eval/results/retrieval.json and eval/results/retrieval.md")


if __name__ == "__main__":
    sys.stdout.reconfigure(errors="replace")
    main()
