| Metric | baseline | optimised | Change |
|---|---|---|---|
| **Accuracy** | 90.0% | 96.7% | +6.7 pts |
| Accuracy (partial = 0.5) | 93.3% | 96.7% | +3.3 pts |
| "I don't know" accuracy | 96.7% | 96.7% | +0.0 pts |
| Faithfulness | 72.3% | 86.7% | +14.3 pts |
| Citation accuracy | 94.9% | 97.8% | +2.9 pts |
| Latency p50 | 5.48 s | 6.54 s | +19% |
| Latency p95 | 21.84 s | 13.56 s | -38% |
| Cost / request | $0.000584 | $0.000283 | -52% |

30 questions, same eval set and judge (openai/gpt-oss-20b).

✅ Accuracy change: 6.7 points → within the 2-point rule.
Best cut in cost or p95: 52% → ✅ reaches the 50% target.
