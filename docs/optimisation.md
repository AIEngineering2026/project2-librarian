# Optimisation report 

**Target (from the brief):** cut cost per request **or** p95 latency by **50%**, losing at most
**2 points** of accuracy on our own eval. Every change is measured before and after with the same test set.

**Result:** ✅ **cost per request −53%** ($0.000574 → $0.000268) with **no accuracy lost** on the hard
test set (14/15 → 14/15). Final version = **E1 + E6** ("low" reasoning effort for both LLMs).

---

## 1. How we measured

`py -m eval.experiment --label NAME [options]` runs, for each experiment, on the **same data**
(4,065 chunks) and the **same questions**:
- **Speed:** end-to-end p50 / p95 latency on 20 questions, plus the average time per step (rewrite / search / rerank / answer).
- **Cost:** average US$ per request from Groq token counts (gpt-oss-120b $0.15 in / $0.75 out, gpt-oss-20b $0.075 in / $0.30 out per 1M tokens).
- **Accuracy (proxy):** 15 hard questions with automatic pass/fail checks (vague, typos, French, multi-part, exceptions, AA vs AAA, "I don't know" traps). The checks were validated against our manual judgement on 8 real answers.

Each experiment changes **one** setting on top of the previous winners. Results: `eval/results/*.json`
and `eval/results/experiments.md`.

---

## 2. Pipeline (baseline)

Question rewrite (gpt-oss-20b) → hybrid search (BM25 + vector) for the original question and each
rewritten query → cross-encoder rerank (ms-marco-MiniLM-L-6-v2) → top 5 chunks → answer
(gpt-oss-120b) with citations → "I don't know" if the best rerank score < 0.

---

## 3. Results

| Version | Change | p50 (s) | p95 (s) | rewrite / search / rerank / answer (s) | Cost / request ($) | Hard-set accuracy | Decision |
|---|---|---|---|---|---|---|---|
| **Baseline** | — | 6.43 | 11.64 | 1.24 / 0.08 / 1.51 / 4.21 | 0.000574 | 14/15 | — |
| **E1** | Rewrite model: `reasoning_effort="low"` | 4.50 | 9.89 | 0.72 / 0.07 / 1.53 / 2.65 | 0.000355 | 14/15 | ✅ Kept |
| **E1 + E6** | + Answer model: `reasoning_effort="low"` | 3.28 | 10.49 | 0.94 / 0.07 / 1.63 / 2.14 | **0.000268** | 14/15 | ✅ **Kept (final)** |
| E1 + E6 + E3 | + Send 3 chunks instead of 5 | 4.23 | 9.65 | 0.58 / 0.06 / 1.75 / 2.49 | 0.000269 | 14/15 | ❌ Dropped (no saving) |

### Before vs after (final version)

| Metric | Before | After | Change |
|---|---|---|---|
| **Cost per request** | $0.000574 | **$0.000268** | **−53%** ✅ target met |
| Cost per 1,000 requests | $0.57 | $0.27 | −53% |
| Monthly cost at 100× (5,000 requests/day) | $86.10 | **$40.20** | −53% |
| p50 latency | 6.43 s | 3.28 s | −49% |
| p95 latency | 11.64 s | 10.49 s | −10% |
| Hard-set accuracy (proxy) | 14/15 | 14/15 | 0 points |
| Official accuracy (124-question eval) | *(Maya)* | *(Maya)* | *(must be ≥ −2 points)* |

---

## 4. What we learned

1. **The hidden cost was "thinking" tokens.** gpt-oss models produce reasoning tokens before the
   visible output, and they are billed as output ($0.75/M for 120b). The rewrite model spent ~2,000
   reasoning tokens to produce a short JSON object. Lowering the reasoning effort (E1, E6) gave the
   whole saving.
2. **Sending fewer chunks (E3) saved nothing.** Passages are *input* tokens ($0.15/M, 5× cheaper than
   output). Going from 5 to 3 chunks did not change the cost ($0.000268 → $0.000269), and it risks
   missing information for multi-part questions, so it was dropped.
   **Lesson:** measure where the cost actually comes from before optimising.
3. **We chose cost as the target metric, not p95.** p95 is driven by the 1–2 slowest requests out
   of 20, which mostly depend on Groq free-tier queueing. It moved up and down between runs
   independently of our changes (e.g. the answer step got faster in E1 although E1 did not change it).
   Cost is computed from token counts, so it is reproducible.
4. **Search is not a bottleneck** (≈0.07 s). The **reranker (~1.5 s on CPU)** is now the largest
   step we control. A next step would be reranking against fewer queries, or skipping the reranker
   when the first search is confident.

---

## 5. Limitations

- The accuracy check here is a **proxy** on 15 hard questions: one question ≈ 7 points, so the
  "max 2 points" rule can only be confirmed with the **full eval (`data/eval.jsonl`, ~124 questions)**,
  run by Maya on both versions.
- Latency comes from **20 requests on the Groq free tier**, so p95 is noisy (shared queue).
- Results vary between runs even at temperature 0 (the rewritten queries differ slightly).
- **Free-tier limit:** 200,000 tokens/day for gpt-oss-120b. Each experiment used ≈ 50,000 tokens, so
  experiments had to be spread across team members' keys. At 100× traffic a paid tier is required.

---

## 6. Not tried (ideas for later)

| Idea | Why not now |
|---|---|
| Skip the rewrite for clear questions (`--skip-rewrite-if-clear`) | Rewrite is already cheap after E1; risk on vague questions |
| Cache repeated questions (`--cache`) | Only helps with repeated traffic; our test questions are unique |
| Raise the "I don't know" threshold | Off-topic questions still reach the answer model, but the threshold must be tuned on the full eval to avoid false refusals |
| Rerank only against the clean question (not every query) | Would cut the ~1.5 s rerank step; needs an accuracy check on multi-part questions |