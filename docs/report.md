# The Librarian: a cited WCAG 2.2 assistant

**CS496 AI Engineering · Project 2 · Dr Abdeldjalil Labed · MedTech · Fall 2026**
**Team:** Mayssa (data & index) · Khadija (pipeline, UI & optimisation) · Maya (evaluation & documentation)

**Summary.** A RAG assistant over 557 W3C pages that answers only from the documents, cites every claim
and refuses when it cannot answer. Hybrid search + reranker finds the right passage in the top 5 for
**93%** of questions. On the generation eval (LLM judge, 30 questions) the final version reaches
**96.7% accuracy**, **98% citation accuracy** and answers **no out-of-scope question**. Week 8 cut the
**cost per request by 52%** with no accuracy lost.

---

## 1. The corpus and its users

**Corpus.** The official **W3C WCAG 2.2** documentation: the WCAG 2.2 Recommendation, the
*Understanding WCAG 2.2* pages and the *Techniques for WCAG 2.2* pages. We scraped **557 pages** and
split them into **4,065 chunks**. The corpus is public, contains no personal data, and is far too
large to fit in one prompt.

**Why this corpus.** Every rule has a numbered success criterion (e.g. SC 1.4.3), so answers can be
checked. The European Accessibility Act (in force since June 2025) makes WCAG compliance a legal
requirement for many digital products, so developers need fast, *trustworthy* answers. A wrong
answer can mean a non-compliant product.

**Users.** Front-end and mobile developers and UI designers, including our own classmates. A typical
question is *"Is an icon-only button allowed?"* or *"How big must a touch target be?"*. Users rarely
use WCAG vocabulary, and that shaped the pipeline (§2.3).

**What the system must do:** answer only from the documents, cite every claim, and say
*"I don't know"* when the documents do not contain the answer.

---

## 2. Pipeline design

```
question → rewrite (gpt-oss-20b) → hybrid search (BM25 + vector) → rerank (cross-encoder)
         → "I don't know" check → answer with citations (gpt-oss-120b) → web UI
```

### 2.1 Chunking and index (offline)
- **Scraping:** requests + BeautifulSoup. We keep title, section and URL as metadata for every chunk.
- **Chunking:** split by heading first, about 500 tokens with a small overlap, keeping text boundaries;
  the chunk size was chosen after comparing several sizes on retrieval.
- **Cleaning:** two problems found during testing and fixed:
  1. The same page existed under two URLs (`…/non-text-contrast` and `…/non-text-contrast.html`), so we deduplicated the URL variants.
  2. Repeated boilerplate sections such as *Key Terms* (identical glossary text on many pages) flooded the results for common words, so the duplicates were removed (4,749 → 4,522 → **4,065 chunks**).
- **Index:** a **BM25** keyword index (`rank_bm25`) plus a **Chroma** vector store with
  `all-MiniLM-L6-v2` embeddings. Both are free, local and fast (search ≈ 25 ms). Chroma was chosen for
  simplicity: one local folder, no server, enough for 4k chunks.

### 2.2 Retrieval
`retrieve(query, k, mode)` supports `bm25`, `vector` and `hybrid`. Hybrid merges the two rankings with
**reciprocal rank fusion (RRF)**. A **cross-encoder reranker** (`ms-marco-MiniLM-L-6-v2`) then reads
each (question, chunk) pair and keeps the **best 5** of 20 candidates.

### 2.3 Question rewriting
Our first version failed on **6 of 15** hard test questions. Every failure used words that are not in
WCAG: *"buttons too small?"* (WCAG says *target size*), *"puzzle CAPTCHA"* (*cognitive function test*),
typos, French, and SC numbers (BM25 splits "1.4.3" into "1", "4", "3"). A small LLM
(**gpt-oss-20b**) now rewrites each question into a clean English question plus 1–3 WCAG search
queries. We search with the **original question and every query**, and each chunk keeps its **best**
rerank score across queries, so a two-part question keeps chunks for both parts. The rewriter may
**not** put answer values in queries (it once invented "icons 4.5:1"), and may give an SC number only
when it is sure. If the rewrite fails, the pipeline falls back to the original question.
**Hard-set result: 8/15 → 14/15.**

### 2.4 Generation and "I don't know"
**gpt-oss-120b** receives the 5 chunks numbered `[1]…[5]` and must:
answer only from them; cite every fact; report exemptions and exceptions; name the conformance level
(A / AA / AAA) and never mix levels; answer in the user's language. Citations are normalised (the model
sometimes writes `【1】` or `【1†L1-L4】`) and mapped back to chunk ids.

"I don't know" has **two layers**:
1. **Reranker threshold (free):** if the best rerank score is below 0, we stop **without calling the LLM**.
   Relevant chunks score about +4 to +10 and off-topic ones about −11.
2. **The LLM itself** refuses when the chunks do not answer. Example: *"What contrast does WCAG 3.0
   require?"* retrieves contrast pages (score 7.4), but the model still refuses because they are about 2.2.

### 2.5 Service
A **FastAPI** server (`POST /api/ask`, `POST /api/feedback`) and a single-page web UI
(designed with Google Stitch, then hand-coded). It shows the answer with clickable citations (hovering
`[n]` highlights the source), the sources, the retrieved passages with relevance scores, the rewritten
search queries, the response time, and 👍/👎 feedback. We chose a custom page over Streamlit because
these interactions are not possible in Streamlit, and the API is also used by the eval scripts.

---

## 3. Retrieval results and ablation

**Eval set:** `data/eval.jsonl` has **112 answerable questions plus unanswerable ones (≈ 10%)**. Each
question has a gold answer and a gold source passage. They were drafted from the corpus and **reviewed
by hand**: duplicates, answers not supported by their passage, and test-rule fragments were dropped or fixed.

**Hit definition.** A retrieved chunk counts only if it **contains the gold passage** (substring, a run
of ≥ 60% of its words, or ≥ 85% of its words in order). URL matching alone is misleading: the whole WCAG
2.2 Recommendation is **one URL** (184 chunks), so "URL-only" recall is inflated (shown for comparison).

| System | R@1 | R@3 | R@5 | R@10 | MRR@10 | URL-only R@5 | Search p50 |
|---|---|---|---|---|---|---|---|
| BM25 only | 0.59 | 0.76 | 0.85 | 0.92 | 0.69 | 0.89 | 12 ms |
| Vector only | 0.47 | 0.69 | 0.72 | 0.80 | 0.58 | 0.79 | 9 ms |
| Hybrid (BM25 + vector, RRF) | 0.56 | 0.79 | 0.87 | **0.96** | 0.69 | 0.91 | 24 ms |
| **Hybrid + reranker** | **0.72** | **0.87** | **0.93** | **0.96** | **0.80** | 0.90 | 803 ms |

**What each part adds:**
- **Vector search alone is the weakest** (R@5 0.72). WCAG text is precise and technical, so exact words
  matter more than general meaning.
- **Hybrid** beats both single methods at depth: R@10 **0.96** vs 0.92 (BM25) and 0.80 (vector), i.e. it
  brings the right passage into the candidate pool. It does not improve the top position (R@1 0.56).
- **The reranker** does the ordering: **R@1 0.56 → 0.72**, MRR 0.69 → 0.80, R@5 0.87 → 0.93. It fixed 10
  questions and broke 3 at k = 5. Cost: ≈ 0.8 s per query on CPU, by far the slowest retrieval step.
- **Caveat:** the eval questions were drafted *from* corpus passages, so they reuse WCAG wording. This
  favours BM25. Real users' questions are vaguer (§2.3), which is why question rewriting matters in
  practice even though this table does not measure it.

**Typical misses:** (1) the same text exists on several pages (e.g. the Recommendation and the
Understanding page), so the "right" text is retrieved from the "wrong" page and counted as a miss; (2)
broad questions (*"main goal of Guideline 1.3"*) retrieve the general introduction; (3) "which criterion
does Technique X relate to" questions retrieve similar technique pages.

---

## 4. Generation results

**Method.** `eval/generation_eval.py` runs `answer()` once per question (answers saved, so the judge can
be rerun without paying for the answers again). An LLM judge (gpt-oss-20b) then scores **correctness**
against the gold answer, **faithfulness** (share of claims supported by the chunks they cite),
**citation accuracy** (does chunk `[n]` say what the sentence claims?) and **"I don't know" accuracy**.

⚠️ **Subset.** Because of Groq's free-tier limit (§6.3), the generation eval was run on the **first
30 questions** of `data/eval.jsonl` (26 answerable, 4 unanswerable), the same questions for both
versions. With 30 questions, one question = 3.3 accuracy points.

| Metric | Baseline | Optimised (Week 8) | Change |
|---|---|---|---|
| **Accuracy** (correct answers + correct "I don't know", all 30) | **90.0%** | **96.7%** | +6.7 pts |
| Accuracy, partial = 0.5 | 93.3% | 96.7% | +3.3 pts |
| Answerable: correct / partial / incorrect / refused (of 26) | 23 / 2 / 0 / 1 | 25 / 0 / 0 / 1 | |
| "I don't know" accuracy | 96.7% | 96.7% | 0 |
| Out-of-scope questions answered anyway | 0 / 4 | 0 / 4 | |
| Faithfulness (claims supported by their cited chunks) | 72.3% | 86.4% | +14.0 pts |
| Fully faithful answers | 52.0% | 76.0% | +24 pts |
| Citation accuracy | 94.9% (59 citations) | 97.8% (46 citations) | +2.9 pts |
| Factual claims with no citation | 10 | 15 | |
| Latency p50 / p95 | 5.48 s / 21.84 s | 6.54 s / 13.56 s | +19% / −38% |
| **Cost per request** | $0.000584 | **$0.000283** | **−52%** |

**Reading the results.**
- **Correctness is high in both versions:** no incorrect answer, and **no out-of-scope question was
  answered**. The baseline's 2 partial answers were on "which criterion does Technique X relate to" questions.
- **Citations are accurate** (95–98%): when the model cites a chunk, the chunk says it.
- **Faithfulness is the weak point**, mostly because of **claims with no citation**: the model adds a
  concluding sentence without `[n]` (e.g. *"This built-in abort mechanism lets users avoid unintended
  clicks."*), which the judge counts as unsupported. In the optimised run, most uncited "claims" come from
  one numbered list where the judge also counted the list numbers ("1.", "2.") as claims, so faithfulness
  is slightly understated. **Next step:** require a citation on every sentence, or drop uncited sentences.
- **False "I don't know":** one per version, on different questions (baseline: *"How is a general flash
  defined?"*; optimised: *"Why is SC 2.4.10 placed at Level AAA?"*), both refused by the LLM although
  relevant chunks were retrieved (rerank score > 8).
- **The optimised version scores higher, but we do not claim it is more accurate.** On 30 questions one
  question = 3.3 points, so +6.7 points is two questions. The safe conclusion is **no accuracy lost**.
  Shorter reasoning may make answers stick closer to the sources (higher faithfulness), but this needs the
  full eval to confirm.
- **Latency** in this run reflects Groq free-tier queueing after hours of experiments (p95 21.8 s in the
  baseline) more than the pipeline itself.

**Hard test set (15 questions written to break the system, auto-scored):** 14/15 in both versions. The
remaining failure: *"Can I use a puzzle CAPTCHA on my login page?"* is answered from SC 1.1.1 (offer an
alternative CAPTCHA) but misses **SC 3.3.8 Accessible Authentication**, so it is correct but incomplete.

---

## 5. Week 8: cheaper and faster

**Target:** cut cost per request or p95 latency by 50%, losing at most 2 accuracy points.
**Method:** `eval/experiment.py`, one change at a time on the same data and the same 20 questions
(speed + cost) plus the 15 hard questions (accuracy proxy).

| Version | Change | p50 | p95 | Cost / request | Hard set | Decision |
|---|---|---|---|---|---|---|
| Baseline | — | 6.43 s | 11.64 s | $0.000574 | 14/15 | — |
| E1 | Rewrite model: reasoning effort "low" | 4.50 s | 9.89 s | $0.000355 | 14/15 | ✅ kept |
| **E1 + E6** | + Answer model: reasoning effort "low" | **3.28 s** | 10.49 s | **$0.000268** | 14/15 | ✅ **final** |
| E1 + E6 + E3 | + 3 chunks instead of 5 | 4.23 s | 9.65 s | $0.000269 | 14/15 | ❌ no saving |

**Result: cost per request −53%** on the speed set and **−52%** in the official eval (target met),
typical wait (p50) **−49%** on the speed set, no accuracy lost on the hard set.
**Official before/after (§4, 30 questions, LLM judge): accuracy 90.0% → 96.7%, so the 2-point rule is met ✅.**

**What we learned:**
- **The hidden cost was reasoning ("thinking") tokens.** gpt-oss models generate reasoning tokens
  billed as *output* ($0.75/M for 120b). The rewrite model spent about 2,000 of them to produce a short
  JSON object. Lowering the reasoning effort gave the whole saving.
- **Sending fewer chunks saved nothing.** Passages are *input* tokens, 5× cheaper than output. Measure
  where the cost comes from before optimising.
- **Cost, not p95, as the target.** p95 = the 1–2 slowest of 20 requests, which depend mostly on the
  Groq free-tier queue. It moved independently of our changes. Cost comes from token counts and is reproducible.
- **Next step:** the reranker (≈ 1.5 s, running against up to 4 queries on CPU) is now the largest step
  we control.

---

## 6. Known failure cases and cost model

### 6.1 Known failure cases
| Case | Example | Status |
|---|---|---|
| Correct but incomplete | Puzzle CAPTCHA → cites 1.1.1, misses 3.3.8 | Open |
| Wrong level cited | "How many times can content flash?" → cites 2.3.2 (AAA) instead of 2.3.1 (A) | Open |
| False "I don't know" | "What does reflow mean?", "How long should users have to read content with a time limit?" | Open |
| Unfaithful answer | "Does a logo need contrast?" → "Yes" (logos are exempt) | Fixed (prompt rule on exceptions) |
| AA/AAA mix-up | "Large text needs 4.5:1" (the AAA value) | Fixed (prompt rule on levels) |
| Same text on several pages | Correct text retrieved from a different page than the gold one | Affects recall measurement |
| Off-topic questions reach the LLM | "Best pizza in Tunis" passes the threshold after rewriting | Open (threshold to tune) |
| Run-to-run variation | Rewrites differ between runs even at temperature 0, so small test sets are unreliable | Mitigated by larger eval |

### 6.2 Cost model (optimised version)
| | Today (≈ 50 questions/day) | At 100× (≈ 5,000 questions/day) |
|---|---|---|
| LLM cost per request | $0.000268 | $0.000268 |
| LLM cost per month | **≈ $0.40** | **≈ $40** |
| Before Week 8 | ≈ $0.86 | ≈ $86 |

Prices: Groq list prices, gpt-oss-120b $0.15 / $0.75 and gpt-oss-20b $0.075 / $0.30 per 1M input /
output tokens. Embeddings, search and reranking run locally (free, CPU). **Not included:** hosting (a
CPU machine with ~2 GB RAM for the models; currently run locally).

### 6.3 Free-tier limit
Groq's free tier allows **200,000 tokens/day for gpt-oss-120b**, about **130 questions per day** per
account. Our experiments and evals exhausted two team members' daily limits, so the generation eval was
limited to a subset (§4). **At 100× traffic a paid tier is required**; the cost model above assumes one.

---

*Repo: `AIEngineering2026/project2-librarian` · details in `docs/design.md`, `docs/optimisation.md`,
`docs/postmortem.md`, `eval/results/`.*