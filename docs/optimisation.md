# Optimisation report — Week 8

**Target (from the brief):** cut cost per request **or** p95 latency by **50%**, losing at most
**2 points** of accuracy on our own eval. Every change is measured before and after with the same test set.

**Result:** ✅ **cost per request −88%** ($0.00308 → $0.000365) **and p95 latency −72%** (35.0 s → 9.8 s),
with **no accuracy lost** on the hard test set (13/15 → 14/15).
Final version = **E8**: answer model **gpt-6-luna** + "low" reasoning effort for both LLMs.
⏳ To be confirmed by the full LLM-judged eval (section 4).

---

## 1. How we measured

`py -m eval.experiment --label NAME [options]` runs each experiment on the **same data**
(4,065 chunks) and the **same questions**:
- **Speed:** end-to-end p50 / p95 latency on the **first 20 questions of `data/eval.jsonl`** (17 answerable,
  3 out-of-scope; identical in every experiment), plus the average time per step (rewrite / search / rerank / answer).
- **Cost:** average US$ per request from the OpenAI token counts, at list prices per 1M tokens (input / output):
  gpt-5-mini $0.25 / $2.00 · gpt-5-nano $0.05 / $0.40 · gpt-6-luna $0.10 / $0.50.
  Reasoning ("thinking") tokens are billed as output and are included. Cached-input discounts are ignored,
  so the costs are slightly **over**-estimated.
- **Accuracy (quick check):** 15 hard questions with automatic pass/fail checks (vague, typos, French,
  multi-part, exceptions, AA vs AAA, "I don't know" traps). The checks were validated against our manual
  judgement on real answers. Used to **screen** settings; the official accuracy is the full eval (section 4).

Each experiment changes **one idea** on top of the previous ones. Experiment names come from our list of
ideas (E1 = rewrite effort, E3 = fewer chunks, E6 = answer effort, E8 = cheaper answer model, E9 = new);
`+` means ideas combined. Results: `eval/results/oa-*.json` and `eval/results/experiments.md`.

---

## 2. Pipeline (baseline)

Question rewrite (**gpt-5-nano**: off-topic check, translation to English, 1–3 search queries) →
hybrid search (BM25 + vector) for the original question and each query → cross-encoder rerank
(ms-marco-MiniLM-L-6-v2) → top 5 chunks → answer (**gpt-5-mini**) with [n] citations.

Three "I don't know" checks: the rewriter marks the question **off-topic** (then no search and no answer
call) · the best rerank score is **< 0** · the answer model itself says "I don't know.".
The off-topic stop is part of every run below, including the baseline.

---

## 3. Results (OpenAI)

| Version | Change | p50 (s) | p95 (s) | rewrite / search / rerank / answer (s) | Cost / request ($) | Hard set | Note |
|---|---|---|---|---|---|---|---|
| **Baseline** | gpt-5-mini answers, default effort | 24.20 | 35.04 | 12.86 / 0.08 / 1.55 / 8.85 | 0.003080 | 13/15 | Before |
| **E1** | Rewrite: `reasoning_effort="low"` | 14.80 | 18.27 | 4.13 / 0.08 / 1.74 / 7.45 | 0.002249 | 11/15 | −27% cost |
| **E1 + E6** | + Answer: `reasoning_effort="low"` | 10.98 | 14.43 | 4.84 / 0.07 / 1.77 / 3.76 | 0.001246 | 12/15 | −60% cost |
| **E1 + E6 (minimal)** | Both efforts `"minimal"` | **4.49** | **5.35** | 1.22 / 0.07 / 1.78 / 1.13 | 0.000462 | 11/15 | ⚡ **Fastest**, loses quality |
| **E8** | E1 + E6 + answer model **gpt-6-luna** | 8.44 | 9.81 | 4.68 / 0.07 / 1.71 / 1.56 | 0.000365 | **14/15** | ✅ **Chosen** |
| **E9** | E8 + rewrite effort `"minimal"` | 5.24 | 6.98 | 1.64 / 0.08 / 1.68 / 1.84 | **0.000194** | 12/15 | 💰 **Cheapest**, loses quality |

### Why E8

Faster (E1 + E6 minimal) and cheaper (E9) settings exist, but they lose 1–2 hard questions compared
with the baseline (7–13 points), more than the 2 points allowed. **E8 is the only setting that is much cheaper and
much faster and at least as accurate as the baseline.**

### Before vs after (final version)

| Metric | Before (baseline) | After (E8) | Change |
|---|---|---|---|
| **Cost per request** | $0.003080 | **$0.000365** | **−88%** ✅ target met |
| Cost per 1,000 requests | $3.08 | $0.37 | −88% |
| Monthly cost today (50 requests/day) | $4.62 | $0.55 | −88% |
| Monthly cost at 100× (5,000 requests/day) | $462.00 | **$54.75** | −88% |
| p50 latency | 24.20 s | 8.44 s | −65% |
| **p95 latency** | 35.04 s | **9.81 s** | **−72%** ✅ target met |
| Hard-set accuracy (quick check) | 13/15 | 14/15 | +1 question |

---

## 4. Official accuracy (full eval) ⏳

Full eval of `data/eval.jsonl` (100+ questions) with Maya's LLM judge, **baseline vs E8**, same questions,
same judge. The judge is **gpt-4.1-mini**, a model used by neither version, so no version grades itself.

| Metric | Baseline | E8 | Change (rule: ≥ −2 pts) |
|---|---|---|---|
| Answer correctness | ⏳ | ⏳ | ⏳ |
| Faithfulness | ⏳ | ⏳ | ⏳ |
| Citation accuracy | ⏳ | ⏳ | ⏳ |
| "I don't know" when it should | ⏳ | ⏳ | ⏳ |

If E8 loses more than 2 points, the fallback is **E1 + E6** (gpt-5-mini, low effort: −60% cost,
−59% p95), which also meets the target.

---

## 5. What we learned

1. **The hidden cost was "thinking" tokens.** In the baseline, the rewrite alone took **12.9 s**:
   gpt-5-nano "thought" for a long time to produce a short JSON object, and thinking is billed as output.
   Lowering the reasoning effort (E1, E6) gave most of the speed gain.
2. **Too little thinking hurts the search.** With `"minimal"` effort the rewriter writes worse search
   queries, so the right passages are found less often (E1 + E6 minimal, E9). `"low"` is the right level.
3. **Bigger is not always better.** gpt-5-mini failed the same two questions in every run (large text +
   icons, 1.4.3 vs 1.4.6): it mixes up the AA and AAA values. gpt-6-luna, which is newer and cheaper,
   passed both. Our task (read 5 passages, quote the right value with a citation) needs careful reading
   more than heavy reasoning.
4. **Search is not a bottleneck** (≈ 0.07 s). After E8, the **rewrite (~4.7 s)** and the **reranker
   (~1.7 s on CPU)** are the largest steps.

**Known failure in E8:** "Does a logo need to meet contrast rules?" The passage with the logo exemption
was not in the top 5, so the model answered that the sources do not cover logos. It invented nothing, but
the answer is incomplete. This is a retrieval miss, not a generation error.

---

## 6. Limitations

- The hard set has **15 questions** (one question ≈ 7 points), so small differences (11 vs 12 vs 13) are
  partly noise. This is why the final decision depends on the full eval (section 4).
- The OpenAI reasoning models used here **do not accept `temperature=0`**, so answers vary slightly
  between runs.
- Latency comes from **20 requests** through the OpenAI API, so p95 depends on the 1–2 slowest requests.
- gpt-5-mini and gpt-5-nano are marked deprecated by OpenAI. Switching the rewrite model is a one-line
  change (`REWRITE_MODEL`), but it would need a new run.

---

## 7. Earlier run on Groq (extra)

Before the course OpenAI key was available, we ran the same method on **Groq** (free tier;
gpt-oss-120b answers, gpt-oss-20b rewrites). Old table: `eval/results/experiments_groq.md`.

| Version | p50 (s) | p95 (s) | Cost / request ($) | Hard set | Decision |
|---|---|---|---|---|---|
| Baseline | 6.43 | 11.64 | 0.000574 | 14/15 | — |
| E1 (rewrite low) | 4.50 | 9.89 | 0.000355 | 14/15 | Kept |
| E1 + E6 (both low) | 3.28 | 10.49 | 0.000268 | 14/15 | **Final on Groq (−53% cost)** |
| E1 + E6 + E3 (3 chunks instead of 5) | 4.23 | 9.65 | 0.000269 | 14/15 | Dropped: no saving |

On the first 30 questions of the full eval (LLM judge), the Groq final version went from 90.0% to 96.7%
correct (faithfulness 72.3% → 86.4%, citation accuracy 94.9% → 97.8%, cost −52%).

**What this shows:** lowering the reasoning effort cut cost by more than half with **two different
providers and model families**, so the result is not specific to one model. **E3** also taught us that
sending fewer passages saves almost nothing, because passages are input tokens, which are much cheaper
than output tokens. We switched provider with one setting (`LLM_PROVIDER=openai|groq`).

---

## 8. Not tried (ideas for later)

| Idea | Why not now |
|---|---|
| Skip the rewrite for clear questions (`--skip-rewrite-if-clear`) | Would also skip the off-topic check and the translation; risky on vague or French questions |
| Cache repeated questions (`--cache`) | Only helps with repeated traffic; our test questions are all different |
| Raise the "I don't know" threshold | Must be tuned on the full eval to avoid refusing good questions (threshold sweep) |
| Rerank against the clean question only | Would cut part of the ~1.7 s rerank step; needs an accuracy check on multi-part questions |
| Skip the reranker when the first search is confident | Same: saves ~1.7 s, needs an accuracy check |