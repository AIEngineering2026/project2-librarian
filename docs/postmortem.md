# Postmortem â€” Project 2: The Librarian (WCAG 2.2 RAG)

CS496 AI Engineering Â· Team project

This document lists what went wrong while building The Librarian, why it happened, how we fixed it,
and what we learned.

---

## 1. Summary

| Area | Problems | Fixed / mitigated | Still open |
|---|---|---|---|
| Data & index | 4 | 4 | 0 |
| Retrieval & generation | 9 | 6 | 3 |
| Evaluation | 5 | 5 | 0 |
| Environment, tooling & deployment | 7 | 6 | 1 |
| Performance & cost | 2 | 2 | 0 |

**Biggest lessons**
1. The first version looked fine on easy questions, but 15 questions written *to break it* showed
   6 failures. Testing with adversarial questions was more useful than testing with questions we
   already knew it could answer.
2. Measure before optimising: the hidden cost was the models' reasoning tokens, not the passages we
   sent them.
3. On a free API tier, tokens are the scarcest resource. Evals must be planned around the daily limit.

---

## 2. Data & index

### 2.1 Duplicate pages under two URLs â€” *fixed*
- **Symptom:** the same chunk appeared twice in the top 5 (`â€¦/non-text-contrast` and
  `â€¦/non-text-contrast.html`), wasting retrieval slots.
- **Cause:** some W3C pages exist under two URL variants and were scraped twice.
- **Fix:** URL-variant deduplication (4,749 â†’ 4,522 chunks).
- **Extra problem:** the fix first stayed on a feature branch, so anyone merging `main` still got the
  duplicates and built an index from the old data. **Lesson:** a fix only counts once it is on `main`.

### 2.2 Repeated "Key Terms" sections drowned out the real rules â€” *fixed*
- **Symptom:** "What is the minimum contrast for normal text?" returned *I don't know*: 4 of the top 5
  chunks were "Key Terms" glossary chunks, and none contained "4.5:1".
- **Cause:** W3C repeats the same glossary text on many Understanding pages. Each copy became a chunk,
  and its common words (contrast, text, minimum) ranked it above the actual success criterion.
- **Fix:** drop duplicate chunks by normalised text; chunker rewritten (â†’ **4,065 chunks**).
- **Lesson:** look at the actual top-k chunks for a few questions before trusting retrieval scores.

### 2.3 Chunks cut in the middle of a sentence â€” *mitigated*
- **Symptom:** some chunks started mid-sentence (e.g. "used as the letter. A wide borderâ€¦").
- **Risk:** a rule or number split across two chunks means no chunk holds the full answer.
- **Fix:** the chunker was rewritten to split on headings first and respect text boundaries. Not
  re-measured on its own, but recall@10 with hybrid search is 0.96 on the final index.

### 2.4 Same text on several pages â€” *known limitation*
- The same success-criterion text appears in the Recommendation, the Understanding page and sometimes a
  Technique page. Retrieval often returns the right text from a different page, which makes citations
  point to a different (but equivalent) page and lowers measured recall (Â§4.2).

---

### 2.5 The first scraper found 2 pages instead of about 550 - *fixed*
- **What happened:** the crawler only followed links ending in `.html`, but the W3C index pages do not use that form. The first run reported 0 and 1 links, and the index had 191 chunks, all from the spec page.
- **Fix:** the crawler now follows links two levels deep under each index page (557 pages).
- **Lesson:** check counts after every step. A small test sample hid the problem.

### 2.6 Chroma did not run on Streamlit Cloud - *fixed*
- **What happened:** Chroma needs a newer SQLite than the cloud provides, and the cloud has no persistent disk to build an index on.
- **Fix:** the vector index is now a committed flat numpy file (`data/index/embeddings.npy`, 6.2 MB) searched with exact cosine similarity, plus BM25 built in memory. Recall matched on the same questions. A hash check refuses to run if the index does not match `chunks.jsonl`.
- **Lesson:** choose the simplest storage the deployment target supports.

### 2.7 Off-topic questions still return results - *known limitation*
- **What happened:** "capital of France" returned three unrelated technique pages. Search never returns nothing.
- **Fix:** none in retrieval. Refusing depends on the reranker score threshold, so "I don't know" has to be a separate decision.

### 2.8 A pull request overwrote a teammate's file - *fixed*
- **What happened:** the cloud-index PR replaced `eval/retrieval_eval.py` with an older copy, so `eval/ablation.py` failed on `main` with an ImportError.
- **Fix:** restored the file from the commit before the overwrite and merged a fix PR.
- **Lesson:** check `git diff origin/main --stat` before every PR, and only change files you own.

## 3. Retrieval & generation

### 3.1 Questions in "user words" returned *I don't know* â€” *fixed*
- **Symptom:** 6 of 15 hard questions failed with *I don't know* although WCAG answers them: vague
  ("buttons too small?"), no WCAG vocabulary ("grey text looks faint"), SC numbers ("1.4.3 vs 1.4.6"),
  typos, French, "puzzle CAPTCHA".
- **Cause:** users don't use WCAG vocabulary, and BM25 splits "1.4.3" into "1", "4", "3". Retrieval found
  nothing relevant, so the threshold correctly refused.
- **Fix:** **question rewriting** (in the brief, skipped in v1): a small LLM turns the question into a
  clean English question + 1â€“3 WCAG search queries; we search with the original question and every
  query, and keep each chunk's best rerank score.
- **Result:** hard set 8/15 â†’ 14/15; French questions answered in French.
- **Lesson:** an "I don't know" rule can hide retrieval failures, so log *why* it refused
  (`low_score` vs `llm_said_idk`).

### 3.2 The rewriter guessed wrong SC numbers and answer values â€” *mitigated*
- **Symptom:** "buttons too small?" was rewritten to "**2.5.5** Target Size (Minimum)" (correct: 2.5.8);
  one query contained a made-up value ("icons 4.5:1").
- **Fix:** the prompt forbids answer values in queries and allows SC numbers only when certain; we always
  also search with the original question.
- **Lesson:** an LLM used *before* retrieval can inject wrong facts; keep it to vocabulary.

### 3.3 Groq JSON mode failed randomly â€” *fixed*
- **Symptom:** `json_validate_failed` on one question; the rewrite fell back and the answer was *I don't know*.
- **Fix:** ask for JSON in the prompt and extract the `{...}` ourselves; fall back to the original
  question on any error.

### 3.4 Unfaithful answer: "Does a logo need to meet contrast rules?" â†’ "Yes" â€” *fixed*
- **Symptom:** logos are explicitly exempt, but the answer said they need 3:1. It had been correct before
  question rewriting was added.
- **Fix:** prompt rule: report exemptions/exceptions and never state a requirement the sources don't
  state for that exact case. The question passes in all later runs.
- **Lesson:** a change that improves most questions can break one that worked â†’ rerun the full test set
  after every change.

### 3.5 AA / AAA values mixed up â€” *fixed*
- **Symptom:** "Large text needs 4.5:1" (the AAA value; AA is 3:1).
- **Fix:** prompt rule: name the level and criterion for each requirement, give AA first, never mix levels.

### 3.6 Answer in the wrong language â€” *fixed*
- **Symptom:** an English question was answered in German.
- **Fix:** the rewriter detects the question's language, and the answer prompt states it explicitly.

### 3.7 Citations in unexpected formats â€” *fixed*
- **Symptom:** correct answers with no citations extracted.
- **Cause:** the model sometimes writes `ã€1ã€‘` or `ã€1â€ L1-L4ã€‘` instead of `[1]`.
- **Fix:** normalise every citation format to `[n]`.

### 3.8 Claims without citations â€” *open*
- **Symptom:** the LLM judge measured faithfulness of 72% (baseline) / 86% (optimised); 10â€“15 factual
  claims per 30 answers had no `[n]`.
- **Cause:** the model adds summarising sentences without a citation. In numbered lists, the judge also
  counted list numbers ("1.", "2.") as separate uncited claims, which slightly understates faithfulness.
- **Next step:** require a citation on every sentence, or drop uncited sentences after generation.

### 3.9 Remaining wrong, incomplete or refused answers â€” *open*
- "Can I use a puzzle CAPTCHA on my login page?" â†’ cites SC 1.1.1 but misses **SC 3.3.8**: correct but
  incomplete (the queries never searched for "accessible authentication").
- "How many times per second can content flash?" â†’ cites 2.3.2 (AAA) instead of 2.3.1 (A).
- False *I don't know* with relevant chunks retrieved (rerank score > 8): "How is a general flash
  defined?", "Why is SC 2.4.10 placed at Level AAA?", "What does reflow mean in WCAG?".
- Off-topic questions ("best pizza in Tunis") sometimes pass the threshold after rewriting and cost an
  answer call before the LLM refuses.

---

## 4. Evaluation

### 4.1 URL matching inflated recall â€” *fixed*
- **Symptom:** matching retrieved chunks to gold answers by URL gave suspiciously high recall.
- **Cause:** the whole WCAG 2.2 Recommendation is **one URL** (184 chunks), so a "URL hit" almost
  always succeeds.
- **Fix:** a hit = a retrieved chunk **contains the gold passage**; the URL-only number is kept but
  labelled (hybrid R@5: 0.91 by URL vs 0.87 by passage).

### 4.2 A loose matching rule matched the wrong pages â€” *fixed*
- **Symptom:** "60% of the passage's words in order" matched boilerplate such as "This technique relates
  to 1.4.4 Resize Text (Advisory)" on unrelated pages.
- **Fix:** stricter rules (substring, a run of â‰¥ 60% of the words, or â‰¥ 85% of the words in order), and
  boilerplate passages found on more than 3 pages only count on their own page.

### 4.3 Drafted eval questions needed heavy review â€” *fixed*
- **Symptom:** drafted questions included duplicates (across files), answers adding facts not in their
  source passage, one wrong answer (3.2.1 On Focus), and test-rule fragments.
- **Fix:** every question was reviewed against its passage; about 14 were dropped and 25 fixed before
  merging `data/eval.jsonl` (112 answerable + unanswerable questions).
- **Lesson:** LLM-drafted eval data must be reviewed; an eval is only as good as its gold answers.

### 4.4 Results changed between runs â€” *mitigated*
- Even at temperature 0, the rewritten queries differed between runs, so the same question could pass
  once and fail the next time. A 15-question check could not detect a 2-point change (1 question â‰ˆ 7
  points). The official before/after therefore used the larger eval set with an LLM judge.

### 4.5 The final generation eval had to use a subset â€” *mitigated*
- Groq's daily limit (Â§6.2) left tokens for only **30 questions** per version. On 30 questions, one
  question = 3.3 points, so the measured *improvement* (+6.7 points) is within noise; the safe conclusion
  is "no accuracy lost". Answers are saved before judging, and both steps resume after a rate limit, so no
  tokens were wasted on reruns.

---

## 5. Environment, tooling & deployment

| Problem | Cause | Fix |
|---|---|---|
| `python` opened the Microsoft Store | Windows app-execution alias | Use the `py` launcher |
| `GroqError: api_key must be set` | `.env` missing / wrong name | `.env` with `GROQ_API_KEY=...` in the project root |
| `.env.example` deleted by accident | Template renamed to `.env` | `git restore .env.example`; `.env` stays git-ignored |
| Commit silently failed, push sent nothing | Git user name/email not configured on a new laptop | `git config --global user.name/email` |
| `DLL load failed â€¦ Application Control policy` (scipy) | Windows 11 **Smart App Control** blocks unsigned ML library DLLs | Turned Smart App Control off |
| Merge editor (Vim) blocked the terminal | Git's default editor | `git config --global core.editor notepad` |
| **No free hosting** â€” *open* | Hugging Face Docker/Gradio Spaces became paid; free tiers elsewhere have too little RAM for the models | Demo runs locally; a temporary public URL is possible with a Cloudflare tunnel; a `Dockerfile` is ready for a paid host |

**Lesson:** "runs from a clean clone" includes a fresh Windows laptop; these steps belong in the README.

---

## 6. Performance & cost

### 6.1 Slow and expensive answers â€” *fixed (Week 8)*
- **Baseline:** p50 6.4 s, p95 11.6 s, $0.000574 per request.
- **Cause found by timing each step:** most time and cost came from the two LLM calls, and specifically
  their **reasoning tokens** (billed as output, $0.75/M for gpt-oss-120b). The rewrite model spent ~2,000
  reasoning tokens to produce a short JSON object.
- **Fix:** `reasoning_effort="low"` for both models â†’ **cost âˆ’52/53%** (target met), p50 âˆ’49% on the
  speed set, no accuracy lost (official eval: 90.0% â†’ 96.7% on 30 questions).
- **Dead end:** sending 3 chunks instead of 5 saved nothing (input tokens are 5Ã— cheaper than output).
- **p95 is noisy:** it depends on Groq free-tier queueing and moved independently of our changes, so cost
  was chosen as the target metric.

### 6.2 Groq free-tier daily limit â€” *mitigated*
- 200,000 tokens/day for gpt-oss-120b â‰ˆ **130 questions per account**. A single experiment used
  â‰ˆ 50,000 tokens; experiments and evals exhausted two accounts' limits in one morning.
- **Fix:** experiments spread across team members' keys; the judge runs on the smaller model (separate
  limit); answers saved to files so the judge can be rerun for free.
- **Lesson:** budget tokens before planning evals. At 100Ã— traffic a paid tier is required.

---

## 7. What went well

- Agreeing on the shared contract first (`chunks.jsonl` format and `retrieve(query, k, mode)`) let the
  pipeline be built in parallel with a **fake retriever**, then switched to the real one by changing
  one import.
- Small, focused test scripts made each problem visible within minutes, and every Week 8 change was
  measured with one command on the same data and questions.
- Two independent safety layers for *I don't know*: the reranker threshold (no LLM call, no cost) and the
  LLM's own refusal. No out-of-scope question was answered in the final eval (0/4).
- The reranker was worth its cost: recall@1 0.56 â†’ 0.72, MRR@10 0.69 â†’ 0.80.

---

## 8. Still open

1. Claims without citations (Â§3.8): enforce a citation on every sentence.
2. False *I don't know* despite relevant chunks, and the CAPTCHA / 3.3.8 case (Â§3.9).
3. Tune the *I don't know* threshold on the full eval (stop off-topic questions before the answer call).
4. Permanent hosting (Â§5).
5. Run the generation eval on the full question set once token budget allows.
