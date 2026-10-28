# Optimisation report — Week 8

**Target (from the brief):** cut cost per request **or** p95 latency by **50%**, losing at most
**2 points** of accuracy on our own eval. Every change is measured before and after with the same test set.

**How we measure:** `py -m eval.latency_cost` (20 questions: Maya's `data/eval.jsonl` first, topped up
with a fixed built-in list). Accuracy is measured with Maya's generation eval on the same version.

---

## 1. Baseline ("before") 

**Pipeline:** question rewrite (gpt-oss-20b) → hybrid search (BM25 + vector) for the original question
and each rewritten query → cross-encoder rerank (ms-marco-MiniLM-L-6-v2) → top 5 chunks →
answer (gpt-oss-120b) with citations → "I don't know" if the best rerank score < 0.

| Metric | Value |
|---|---|
| Requests measured | 20 |
| **p50 latency (end to end)** | **4.29 s** |
| **p95 latency (end to end)** | **11.47 s** |
| Avg prompt tokens (answer model) | 1,143 |
| Avg completion tokens (answer model) | 229 |
| "I don't know" answers | 5 / 20 |
| **Cost per request** | **$0.000522** |
| Cost per 1,000 requests | $0.52 |
| Monthly cost today (50 requests/day) | $0.78 |
| **Monthly cost at 100× (5,000 requests/day)** | **$78.35** |

Prices used (US$ per 1M tokens, Groq list prices — verify on groq.com/pricing):
gpt-oss-120b $0.15 in / $0.75 out · gpt-oss-20b $0.075 in / $0.30 out.

### What the baseline shows
1. **The rewrite step is a large hidden cost.** "What is the capital of Tunisia?" used 0 answer tokens
   but still cost $0.00064 — entirely from the rewrite call. gpt-oss-20b spends ~2,000 reasoning tokens
   to produce a short JSON object. It also adds latency to every request.
2. **Off-topic questions still reach the answer model.** "Best pizza in Tunis" and "build a Kubernetes
   cluster" each sent ~1,300 tokens to gpt-oss-120b only to get "I don't know". The rerank threshold
   (0.0) lets them through after rewriting.
3. **The 5 chunks are most of the prompt.** ~1,100 of ~1,150 prompt tokens are retrieved passages.
4. **Latency varies a lot** (2.4 s → 11.7 s) — partly Groq free-tier queueing, partly reasoning length.

---

## 2. Planned experiments (one change at a time, measured before/after)

| # | Change | Expected effect | Risk to accuracy |
|---|---|---|---|
| E1 | `reasoning_effort="low"` for the rewrite call | Big cut in rewrite tokens and latency | Low — rewriting is easy |
| E2 | Skip the rewrite when the question already contains WCAG vocabulary or an SC number | Fewer LLM calls | Medium — must keep vague questions working |
| E3 | Send 3 chunks instead of 5 | ~40% fewer answer prompt tokens | Medium — multi-part questions need more chunks |
| E4 | Raise the "I don't know" threshold (tune on the eval set) | No answer call for off-topic questions | Medium — more false "I don't know" |
| E5 | Cache repeated questions (exact match) | ~0 cost and latency on repeats | None |
| E6 | `reasoning_effort="low"` for the answer call | Lower latency and output tokens | Medium — check faithfulness |
| E7 | Skip the reranker when the first search is confident | Lower latency | Medium |

---

## 3. Results ("after")

*(to fill in Week 8: for each experiment — p50, p95, cost per request, accuracy, kept or reverted)*

| Version | p50 | p95 | Cost / request | Accuracy | Kept? |
|---|---|---|---|---|---|
| Baseline | 4.29 s | 11.47 s | $0.000522 | *(Maya's eval)* | — |
| + E1 | | | | | |
| + … | | | | | |

---

## 4. Final comparison

*(before vs after, % change in cost and p95, accuracy change in points)*