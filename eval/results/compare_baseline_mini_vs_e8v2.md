| Metric | baseline_mini | e8v2 | Change |
|---|---|---|---|
| **Accuracy** | 73.8% | 80.3% | +6.6 pts |
| Accuracy (partial = 0.5) | 79.1% | 86.9% | +7.8 pts |
| "I don't know" accuracy | 86.1% | 95.1% | +9.0 pts |
| Faithfulness | 98.9% | 97.1% | -1.8 pts |
| Citation accuracy | 99.1% | 98.6% | -0.5 pts |
| Latency p50 | 24.73 s | 9.4 s | -62% |
| Latency p95 | 34.7 s | 12.78 s | -63% |
| Cost / request | $0.003214 | $0.000404 | -87% |

122 questions, same eval set and judge (gpt-4.1-mini).

✅ Accuracy change: 6.6 points → within the 2-point rule.
Best cut in cost or p95: 87% → ✅ reaches the 50% target.
