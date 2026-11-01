| Metric | baseline_mini | e8 | Change |
|---|---|---|---|
| **Accuracy** | 74.2% | 75.8% | +1.6 pts |
| Accuracy (partial = 0.5) | 79.4% | 84.3% | +4.8 pts |
| "I don't know" accuracy | 86.3% | 95.2% | +8.9 pts |
| Faithfulness | 98.5% | 90.9% | -7.6 pts |
| Citation accuracy | 99.1% | 98.0% | -1.1 pts |
| Latency p50 | 24.68 s | 8.88 s | -64% |
| Latency p95 | 34.67 s | 12.6 s | -64% |
| Cost / request | $0.003208 | $0.000387 | -88% |

124 questions, same eval set and judge (gpt-4.1-mini).

✅ Accuracy change: 1.6 points → within the 2-point rule.
Best cut in cost or p95: 88% → ✅ reaches the 50% target.
