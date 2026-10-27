# Postmortem — Project 2: The Librarian (WCAG 2.2 RAG)

CS496 AI Engineering · Team: Mayssa (data & index), Khadija (pipeline & deploy), Maya (eval & docs)

This document lists what went wrong while building The Librarian, why it happened, how we fixed it,
and what we learned. It is updated as the project goes on (newest problems at the end of each section).

---

## 1. Summary

| Area | Problems found | Fixed | Still open |
|---|---|---|---|
| Data & index | 3 | 1 | 2 |
| Retrieval & generation | 6 | 5 | 1 |
| Environment & tooling | 5 | 5 | 0 |
| Performance | 1 | 0 | 1 (Week 8) |

**Biggest lesson:** the first version looked like it worked on easy questions, but a small set of
15 harder questions showed that 6 of them failed. Testing with questions written to *break* the
system was more useful than testing with questions we already knew it could answer.

---

## 2. Data & index problems

### 2.1 Repeated "Key Terms" sections drowned out the real rules — *open*
- **Symptom:** "What is the minimum contrast for normal text?" returned *I don't know*. 4 of the
  top 5 retrieved chunks were "Key Terms" glossary chunks, and none contained "4.5:1".
- **Cause:** W3C repeats the same glossary text at the bottom of many Understanding pages. Each copy
  became its own chunk, and because it contains common words (contrast, text, minimum), it ranked
  above the actual success criterion.
- **Fix (planned):** drop repeated sections / deduplicate chunks by normalised text (data side).
- **Lesson:** look at the actual top-k chunks for a few questions before trusting retrieval scores.

### 2.2 Duplicate pages under two URLs — *fixed*
- **Symptom:** the same chunk appeared twice in the top 5 (e.g. `non-text-contrast` and
  `non-text-contrast-html`), wasting retrieval slots.
- **Cause:** some W3C pages exist under two URL variants and were scraped twice.
- **Fix:** URL-variant deduplication (4,749 → 4,522 chunks).
- **Extra problem:** the dedupe commit was on the data branch but not on `main`, so a teammate who
  merged `main` still had the duplicates. **Lesson:** fixes only count once they are on `main`.

### 2.3 Chunks cut in the middle of a sentence — *open*
- **Symptom:** some chunks start mid-sentence (e.g. "used as the letter. A wide border…").
- **Risk:** if a rule or a number is split across two chunks, no single chunk contains the full answer.
- **Fix (planned):** split on headings first, then on sentence/paragraph boundaries, with a small overlap.

---

## 3. Retrieval & generation problems

### 3.1 Questions in "user words" returned *I don't know* — *fixed*
- **Symptom:** on our 15 hard test questions, 6 failed with *I don't know* although WCAG answers them:
  vague ("buttons too small?"), no WCAG vocabulary ("grey text looks faint"), SC numbers
  ("1.4.3 vs 1.4.6"), typos ("minimun constrast for txt"), French, and "puzzle CAPTCHA".
- **Cause:** users don't use WCAG vocabulary ("target size", "contrast ratio", "cognitive function
  test"). Keyword search also splits "1.4.3" into "1", "4", "3". Retrieval found nothing relevant, the
  reranker scored everything low, and the threshold correctly returned *I don't know*.
- **Fix:** added **question rewriting** (listed in the brief, skipped in v1): a small LLM
  (gpt-oss-20b) turns the question into a clean English question + 1–3 WCAG search queries. We search
  with the original question and every query, and rerank using the best score per chunk.
- **Result:** 8/15 → **13/15** correct on the hard set. French questions are now answered in French.
- **Lesson:** the "I don't know" rule can hide retrieval failures; log *why* it refused
  (`low_score` vs `llm_said_idk`).

### 3.2 The rewriter guessed wrong success criterion numbers and answer values — *mitigated*
- **Symptom:** "buttons too small?" was rewritten to "**2.5.5** Target Size (Minimum)" (the correct
  SC is 2.5.8), and one query contained a made-up value ("icons 4.5:1").
- **Cause:** the rewrite model uses its own memory to add WCAG terms, and that memory can be wrong.
- **Fix:** the prompt now forbids putting answer values in queries and allows SC numbers only when
  certain. We also always search with the original question, so a bad rewrite cannot remove good results.
- **Lesson:** an LLM used *before* retrieval can inject wrong facts; keep it to vocabulary, not answers.

### 3.3 Groq JSON mode failed randomly — *fixed*
- **Symptom:** `json_validate_failed` on "Can I use a puzzle CAPTCHA on my login page?"; the rewrite
  fell back to the raw question and the answer was *I don't know*.
- **Cause:** Groq's `response_format=json_object` sometimes rejects gpt-oss output.
- **Fix:** ask for JSON in the prompt and extract the `{...}` part ourselves; on any error, fall back
  to the original question so the pipeline never crashes.

### 3.4 Unfaithful answer: "Does a logo need to meet contrast rules?" → "Yes" — *open*
- **Symptom:** the system answered that logos must meet 3:1, but WCAG explicitly exempts logos.
  The same question was answered correctly before question rewriting was added.
- **Cause (likely):** the rewrite steered retrieval towards general 1.4.11 Non-text Contrast passages,
  and the model generalised a rule to a case the sources exempt.
- **Fix (in progress):** answer prompt now says to report exemptions/exceptions and never state a
  requirement the sources don't state for that exact case. Must be confirmed by the faithfulness eval.
- **Lesson:** a change that improves most questions can break one that worked before → always rerun
  the full test set after every change.

### 3.5 Citations in unexpected formats — *fixed*
- **Symptom:** citations were lost (`Cited: []`) although the answer was correct.
- **Cause:** the model sometimes writes `【1】` or `【1†L1-L4】` instead of `[1]`.
- **Fix:** normalise every citation format to `[n]` before extracting chunk ids; the prompt asks for
  ASCII brackets.

### 3.6 Wrong page cited before reranking — *fixed*
- **Symptom:** a correct "4.5:1" answer cited the 1.4.6 *Contrast (Enhanced)* page instead of 1.4.3.
- **Fix:** cross-encoder reranker (retrieve 20 → keep 5). After reranking, all top 5 chunks for the
  contrast question came from the correct page.
- **Note:** reranker scores separate relevant (+4 to +10) from irrelevant (≈ −11) questions clearly,
  so the *I don't know* threshold was set at 0.

### 3.7 Remaining wrong or incomplete answers — *open*
- "Can I use a puzzle CAPTCHA on my login page?" answers correctly from SC 1.1.1 (offer an alternative
  CAPTCHA) but misses **SC 3.3.8 Accessible Authentication**, the most relevant rule: the rewritten
  queries never searched for "accessible authentication / cognitive function test". *Correct but incomplete.*
- "How many times per second can content flash?" cites SC 2.3.2 (AAA) instead of SC 2.3.1 (Level A).
- False *I don't know*: "What does reflow mean in WCAG?" (SC 1.4.10) and "How long should users have
  to read content with a time limit?" (SC 2.2.1).
- **Lesson:** results changed between runs even with temperature 0 (the rewrites differ), so a
  15-question check is not enough to judge a change — the 100+ question eval is needed.

---

## 4. Environment & tooling problems (new laptop, Windows 11)

| Problem | Cause | Fix |
|---|---|---|
| `python` opened the Microsoft Store | Windows app-execution alias | Use the `py` launcher |
| `GroqError: api_key must be set` | `.env` missing / wrong name | Recreate `.env` with `GROQ_API_KEY=...` in the project root |
| `.env.example` deleted by accident | Template renamed to `.env` | `git restore .env.example`; `.env` stays git-ignored |
| Commit silently failed, push sent nothing | Git user name/email not configured | `git config --global user.name/email` |
| `DLL load failed … Application Control policy has blocked this file` (scipy) | Windows 11 **Smart App Control** blocks unsigned ML library DLLs | Turned Smart App Control off |

**Lesson:** "runs from a clean clone" includes a fresh laptop. These steps belong in the README setup section.

---

## 5. Performance — *open (Week 8)*

- End-to-end latency on the hard test set: **about 3 s to 17 s** per question.
- **Causes:** two LLM calls per question (rewrite + answer), gpt-oss reasoning tokens, Groq free-tier
  queueing, and reranking up to 4 queries × candidates on CPU.
- **Ideas for Week 8:** skip the rewrite when the question already uses WCAG vocabulary or an SC number;
  lower reasoning effort; send 3 chunks instead of 5; cache repeated questions; skip the reranker when
  the first search is confident. Every change will be measured before/after with `eval/latency_cost.py`.

---

## 6. What went well

- Agreeing on the shared contract first (`chunks.jsonl` format and `retrieve(query, k, mode)`) let the
  pipeline be built in parallel with a **fake retriever**, then switched to the real one by changing
  one import.
- Small, focused test scripts (`py -m src.pipeline`, `eval/try_questions.py`) made each problem
  visible within minutes.
- Two independent safety layers for *I don't know*: the reranker threshold (no LLM call, no cost) and
  the LLM's own refusal. Example: "What contrast does WCAG 3.0 require?" retrieved contrast pages
  (score 7.4) but the model still refused, because the sources are about WCAG 2.2.

---

## 7. Open issues (to close before the demo)

1. Drop repeated "Key Terms" chunks and fix mid-sentence splits (data).
2. Confirm the logo faithfulness fix with the generation eval / LLM judge.
3. Week 8 latency/cost reduction with before/after numbers.

---

## 8. Team sections

### Mayssa — data & index
*(to add: scraping/cleaning problems, chunk-size experiments 300/500/800, index choices)*

### Maya — eval & docs
*(to add: eval set construction, judge disagreements, user feedback findings)*