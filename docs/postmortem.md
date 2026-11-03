# Postmortem: Project 2, The Librarian (WCAG 2.2 RAG)

CS496 AI Engineering · Team project

This document lists what went wrong while building The Librarian, why it happened, how we fixed it,
and what we learned.

---

## 1. Summary

| Area | Problems | Fixed / mitigated | Still open |
|---|---|---|---|
| Data & index | 8 | 7 | 1 |
| Retrieval & generation | 13 | 12 | 1 |
| Evaluation | 6 | 6 | 0 |
| Environment, tooling & deployment | 7 | 7 | 0 |
| Performance & cost | 3 | 3 | 0 |

**Biggest lessons**
1. The first version looked fine on easy questions, but 15 questions written *to break it* showed
   7 failures. Testing with adversarial questions was more useful than testing with questions we
   already knew it could answer.
2. Measure before optimising: the hidden cost was the models' reasoning tokens, not the passages we
   sent them.
3. Every safety rule needs its own test: two of our fixes (a faithfulness filter and an automatic
   check) first did the opposite of what we wanted, and only the measurements showed it.

---

## 2. Data & index

### 2.1 Duplicate pages under two URLs (*fixed*)
- **Symptom:** the same chunk appeared twice in the top 5 (`…/non-text-contrast` and
  `…/non-text-contrast.html`), wasting retrieval slots.
- **Cause:** some W3C pages exist under two URL variants and were scraped twice.
- **Fix:** URL-variant deduplication (4,749 → 4,522 chunks).
- **Extra problem:** the fix first stayed on a feature branch, so anyone merging `main` still got the
  duplicates and built an index from the old data. **Lesson:** a fix only counts once it is on `main`.

### 2.2 Repeated "Key Terms" sections drowned out the real rules (*fixed*)
- **Symptom:** "What is the minimum contrast for normal text?" returned *I don't know*: 4 of the top 5
  chunks were "Key Terms" glossary chunks, and none contained "4.5:1".
- **Cause:** W3C repeats the same glossary text on many Understanding pages. Each copy became a chunk,
  and its common words (contrast, text, minimum) ranked it above the actual success criterion.
- **Fix:** drop duplicate chunks by normalised text; chunker rewritten (→ **4,065 chunks**).
- **Lesson:** look at the actual top-k chunks for a few questions before trusting retrieval scores.

### 2.3 Chunks cut in the middle of a sentence (*mitigated*)
- **Symptom:** some chunks started mid-sentence (e.g. "used as the letter. A wide border…").
- **Risk:** a rule or number split across two chunks means no chunk holds the full answer.
- **Fix:** the chunker splits on headings first and packs whole sentences (up to 375 words, two-sentence
  overlap). Mid-sentence starts fell from 13.6% to 5.0%; hybrid recall@10 is 0.96 on the final index.

### 2.4 Same text on several pages (*known limitation*)
- The same success-criterion text appears in the Recommendation, the Understanding page and sometimes a
  Technique page. Retrieval often returns the right text from a different page, which makes citations
  point to a different (but equivalent) page and lowers measured recall (§4.2).

### 2.5 The first scraper found 2 pages instead of about 550 (*fixed*)
- **What happened:** the crawler only followed links ending in `.html`, but the W3C index pages do not
  use that form. The first run reported 0 and 1 links, and the index had 191 chunks, all from the spec page.
- **Fix:** the crawler now follows links two levels deep under each index page (557 pages).
- **Lesson:** check counts after every step. A small test sample hid the problem.

### 2.6 Chroma was hard to run on Streamlit Cloud (*fixed*)
- **What happened:** Chroma needed a SQLite workaround (`pysqlite3-binary`) on Streamlit Cloud, and the
  app rebuilt the index at every start because the cloud has no persistent disk.
- **Fix:** the committed flat numpy file removes both: the vector index is `data/index/embeddings.npy`
  (6.2 MB), searched with exact cosine similarity, plus BM25 built in memory. Recall matched on the same
  questions. A hash check refuses to run if the index does not match `chunks.jsonl`.
- **Lesson:** choose the simplest storage the deployment target supports.

### 2.7 Off-topic questions still return results (*mitigated*)
- **What happened:** "capital of France" returned three unrelated technique pages. Search never returns
  nothing.
- **Fix:** refusing is a separate decision: the rewriter now flags off-topic questions before any search
  (§3.10), and the reranker score threshold catches the rest.

### 2.8 A pull request overwrote a teammate's file (*fixed*)
- **What happened:** the cloud-index PR replaced `eval/retrieval_eval.py` with an older copy, so
  `eval/ablation.py` failed on `main` with an ImportError.
- **Fix:** restored the file from the commit before the overwrite and merged a fix PR.
- **Lesson:** check `git diff origin/main --stat` before every PR, and only change files you own.

---

## 3. Retrieval & generation

### 3.1 Questions in "user words" returned *I don't know* (*fixed*)
- **Symptom:** 7 of 15 hard questions failed (6 with *I don't know*) although WCAG answers them: vague
  ("buttons too small?"), no WCAG vocabulary ("grey text looks faint"), SC numbers ("1.4.3 vs 1.4.6"),
  typos, French, "puzzle CAPTCHA".
- **Cause:** users don't use WCAG vocabulary, and BM25 splits "1.4.3" into "1", "4", "3". Retrieval found
  nothing relevant, so the threshold correctly refused.
- **Fix:** **question rewriting** (in the brief, skipped in v1): a small LLM turns the question into a
  clean English question + 1–3 WCAG search queries; we search with the original question and every
  query, and keep each chunk's best rerank score.
- **Result:** hard set 8/15 → 14/15; French questions answered in French.
- **Lesson:** an "I don't know" rule can hide retrieval failures, so log *why* it refused
  (`off_topic`, `low_score` or `llm_said_idk`).

### 3.2 The rewriter guessed wrong SC numbers and answer values (*mitigated*)
- **Symptom:** "buttons too small?" was rewritten to "**2.5.5** Target Size (Minimum)" (correct: 2.5.8);
  one query contained a made-up value ("icons 4.5:1").
- **Fix:** the prompt forbids answer values in queries and allows SC numbers only when certain; we always
  also search with the original question.
- **Lesson:** an LLM used *before* retrieval can inject wrong facts; keep it to vocabulary.

### 3.3 The rewriter's JSON reply failed randomly (*fixed*)
- **Symptom:** on Groq, JSON mode failed (`json_validate_failed`) on one question; the rewrite fell back
  and the answer was *I don't know*.
- **Fix:** ask for JSON in the prompt and extract the `{...}` ourselves; see §3.12 for the retry.

### 3.4 Unfaithful answer: "Does a logo need to meet contrast rules?" → "Yes" (*fixed*)
- **Symptom:** logos are explicitly exempt, but the answer said they need 3:1. It had been correct before
  question rewriting was added.
- **Fix:** prompt rule: report exemptions/exceptions and never state a requirement the sources don't
  state for that exact case.
- **Lesson:** a change that improves most questions can break one that worked, so rerun the full test
  set after every change.

### 3.5 AA / AAA values mixed up (*fixed*)
- **Symptom:** "Large text needs 4.5:1" (the AAA value; AA is 3:1).
- **Fix:** prompt rule: name the level and criterion for each requirement, give AA first, never mix levels.

### 3.6 Answer in the wrong language (*fixed*)
- **Symptom:** an English question was answered in German.
- **Fix:** the rewriter detects the question's language, and the answer prompt states it explicitly.

### 3.7 Citations in unexpected formats (*fixed*)
- **Symptom:** correct answers with no citations extracted.
- **Cause:** the model sometimes writes `【1】` or `【1†L1-L4】` instead of `[1]`.
- **Fix:** normalise every citation format to `[n]`.

### 3.8 Claims without citations (*fixed, re-measurement pending*)
- **Symptom:** in the first (Groq) eval, faithfulness was 72% / 86%: the model added summarising
  sentences without `[n]`. After the switch to OpenAI, the optimised version (E8) dropped from 98.5% to
  90.9% faithfulness.
- **Cause (found by reading the judged answers):** mostly an uncited first sentence ("Yes.", a
  definition) before the cited one, and refusals written as "The sources do not state… I don't know."
  that were counted as answers.
- **Fix:** the prompt requires a citation on every sentence, including the first; uncited closing
  sentences are removed after generation; an answer that says "I don't know" and cites nothing now
  counts as a refusal. The full eval is being re-run to measure the effect.

### 3.9 Remaining wrong, incomplete or refused answers (*open*)
- "Can I use a puzzle CAPTCHA on my login page?" cites SC 1.1.1 but misses **SC 3.3.8**: correct but
  incomplete. The 3.3.8 passage is rarely in the top 5 (it failed in 6 of 8 test runs).
- "What's the difference between 1.4.3 and 1.4.6?" sometimes misses the 7:1 passage.
- With low reasoning effort, answers are shorter and more often partial (21 vs 4 partial answers in the
  full eval), although overall accuracy went up.

### 3.10 The rewriter invented WCAG queries for off-topic questions (*fixed*)
- **Symptom:** for "What is the best pizza in Tunis?", the rewriter produced "non-text contrast",
  "keyboard accessible navigation" and "focus visible". Those queries found real passages (rerank score
  ≈ 8), so the threshold let the question through and an answer call was paid before the model refused.
- **Fix:** the rewriter first decides whether the question is about web accessibility (`off_topic`).
  If not, the pipeline answers "I don't know" right away: no search, no reranking, no answer call.
- **Lesson:** a model asked to always produce queries will produce them, even when it should not.

### 3.11 The first faithfulness filter removed the main answer (*fixed*)
- **Symptom:** the first version of the filter removed *every* uncited sentence. On "What contrast do
  large text and icons need?", the model had forgotten the citation on the two main lines, so the filter
  deleted them and left only the exceptions.
- **Fix:** the filter now only removes uncited sentences at the *end* of the answer (the model's own
  conclusions); uncited sentences before the last citation are kept.
- **Lesson:** a safety filter that is too strict can do more harm than the problem it targets.

### 3.12 Empty rewriter replies sent French questions to search in French (*fixed*)
- **Symptom:** in one run, "Quel est le contraste minimum pour le texte ?" was answered *I don't know*.
  The search had used the original French question.
- **Cause:** the rewriter returned no usable queries, so the pipeline fell back to the original question.
  For an English question this is almost harmless; for a French one, it searches an English corpus in French.
- **Fix:** retry the rewrite once before falling back, and record retries and failures in the results so
  the eval can count them.

### 3.13 Switching provider in the last week (*fixed*)
- **What happened:** the Groq free tier ran out (§6.2), and the course OpenAI key arrived in the final week.
- **Fix:** the pipeline reads the provider from one setting (`LLM_PROVIDER`), so the switch changed no
  pipeline logic. OpenAI's reasoning models do not accept `temperature=0`, so answers vary slightly
  between runs, and the Week 8 experiments were repeated on OpenAI.

---

## 4. Evaluation

### 4.1 URL matching inflated recall (*fixed*)
- **Symptom:** matching retrieved chunks to gold answers by URL gave suspiciously high recall.
- **Cause:** the whole WCAG 2.2 Recommendation is **one URL** (184 chunks), so a "URL hit" almost
  always succeeds.
- **Fix:** a hit = a retrieved chunk **contains the gold passage**; the URL-only number is kept but
  labelled.

### 4.2 A loose matching rule matched the wrong pages (*fixed*)
- **Symptom:** "60% of the passage's words in order" matched boilerplate such as "This technique relates
  to 1.4.4 Resize Text (Advisory)" on unrelated pages.
- **Fix:** stricter rules (substring, a run of ≥ 60% of the words, or ≥ 85% of the words in order), and
  boilerplate passages found on more than 3 pages only count on their own page.

### 4.3 Drafted eval questions needed heavy review (*fixed*)
- **Symptom:** drafted questions included duplicates (across files), answers adding facts not in their
  source passage, one wrong answer (3.2.1 On Focus), and test-rule fragments.
- **Fix:** every question was reviewed against its passage; questions were dropped or fixed before
  merging `data/eval.jsonl`.
- **Lesson:** LLM-drafted eval data must be reviewed; an eval is only as good as its gold answers.

### 4.4 Results changed between runs (*mitigated*)
- The same setting scored 14/15, 13/15 and 11/15 on the hard set in different runs, because the
  rewritten queries and the answers vary. On 15 questions, one question is about 7 points, so the hard
  set was only used to compare settings quickly; decisions were made on the full eval.

### 4.5 An automatic check marked a correct answer wrong (*fixed*)
- **Symptom:** "Does disabled button text need good contrast?" was answered correctly ("does not require
  inactive user interface components… to meet contrast requirements") but failed, because the check only
  accepted "no", "exempt" or "not required".
- **Fix:** the check also accepts equivalent wordings, and all saved runs were re-scored with the same
  rule (`eval/rescore.py`), with no new model calls.

### 4.6 The first generation eval had to use a subset (*fixed*)
- Groq's daily limit (§6.2) left tokens for only 30 questions per version. With the OpenAI key, the
  before/after comparison was run on the full set (124 questions). The final set has 122 questions after
  two document-structure questions were removed; the Week 8 numbers refer to the 124-question run.

---

## 5. Environment, tooling & deployment

| Problem | Cause | Fix |
|---|---|---|
| `python` opened the Microsoft Store | Windows app-execution alias | Use the `py` launcher |
| `GroqError: api_key must be set` | `.env` missing / wrong name | `.env` with the API key in the project root |
| `.env.example` deleted by accident | Template renamed to `.env` | `git restore .env.example`; `.env` stays git-ignored |
| Commit silently failed, push sent nothing | Git user name/email not configured on a new laptop | `git config --global user.name/email` |
| `DLL load failed … Application Control policy` (scipy) | Windows 11 **Smart App Control** blocks unsigned ML library DLLs | Turned Smart App Control off |
| Merge editor (Vim) blocked the terminal | Git's default editor | `git config --global core.editor notepad` |
| No free hosting with enough memory | Hugging Face Spaces became paid; Render's free tier (512 MB) and Vercel functions (250 MB) are too small for the models | Deployed on **Streamlit Community Cloud**; votes are saved to a GitHub gist because the cloud deletes local files on restart |

**Lesson:** "runs from a clean clone" includes a fresh Windows laptop; these steps belong in the README.

---

## 6. Performance & cost

### 6.1 Slow and expensive answers (*fixed, Week 8*)
- **Cause found by timing each step:** most time and cost came from the two LLM calls, and specifically
  their **reasoning tokens**, billed as output. In the OpenAI baseline, the rewrite step alone took
  12.9 s on average to produce a short JSON object.
- **Fix:** `reasoning_effort="low"` for both models, and gpt-6-luna instead of gpt-5-mini for answers.
  Full eval (124 questions): **cost −88%**, **p95 −64%** (34.7 s → 12.6 s), accuracy 74.2% → 75.8%.
- **Dead ends:** sending 3 chunks instead of 5 saved nothing (input tokens are much cheaper than output);
  "minimal" reasoning effort was the fastest setting but wrote worse search queries and lost quality.
- On Groq, the same method had already cut cost by 53% with no accuracy lost, so the result holds
  across two providers.

### 6.2 Groq free-tier daily limit (*fixed*)
- 200,000 tokens/day for gpt-oss-120b ≈ **130 questions per account**. A single experiment used
  ≈ 50,000 tokens; experiments and evals exhausted two accounts' limits in one morning.
- **Fix at the time:** experiments spread across team members' keys, the judge on a smaller model, and
  answers saved to files so the judge could be rerun for free. **Final fix:** the course OpenAI key.
- **Lesson:** budget tokens before planning evals.

### 6.3 Paying for questions that should never reach the answer model (*fixed*)
- Off-topic questions used to cost a rewrite, a search and an answer call (§3.10). They now stop after
  the rewrite, which costs a fraction of a normal question.

---

## 7. What went well

- Agreeing on the shared contract first (`chunks.jsonl` format and `retrieve(query, k, mode)`) let the
  pipeline be built in parallel with a **fake retriever**, then switched to the real one by changing
  one import. The same contract let the index move from Chroma to a numpy file without touching the
  pipeline.
- Small, focused test scripts made each problem visible within minutes, and every Week 8 change was
  measured with one command on the same data and questions.
- Three independent safety layers for *I don't know*: the off-topic check (no search), the reranker
  threshold (no answer call) and the model's own refusal. In the full eval, no out-of-scope question
  received a real answer (three refusals were miscounted as answers, §3.8).
- The reranker was worth its cost: recall@1 0.56 → 0.72, MRR@10 0.69 → 0.80.

---

## 8. Still open

1. Faithfulness after the second fix (§3.8): the full eval is being re-run.
2. The CAPTCHA / 3.3.8 case and other incomplete answers (§3.9).
3. Shorter, partial answers at low reasoning effort: a trade-off accepted for the −88% cost.
4. The eval questions were drafted from the passages, which probably favours keyword search; a set of
   hand-written questions would test this.
