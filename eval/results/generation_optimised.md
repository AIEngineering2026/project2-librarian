## Generation eval: `optimised`

Settings: `{"MODEL": "openai/gpt-oss-120b", "REWRITE_MODEL": "openai/gpt-oss-20b", "RERANKER": "cross-encoder/ms-marco-MiniLM-L-6-v2", "CANDIDATES": 20, "PER_QUERY": 10, "TOP_K": 5, "MIN_SCORE": 0.0, "REWRITE_EFFORT": "low", "ANSWER_EFFORT": "low"}` · judge: openai/gpt-oss-20b

| Metric | Value |
|---|---|
| **Accuracy** (correct answers + correct "I don't know", all 30 questions) | **96.7%** |
| Accuracy, partial = 0.5 | 96.7% |
| Correct on answerable (26) | 96.2% (correct 25 · partial 0 · incorrect 0 · refused 1) |
| "I don't know" accuracy | 96.7% |
| False "I don't know" (answerable refused) | 1 (0 by the score threshold) |
| Out-of-scope questions answered anyway | 0 / 4 |
| Faithfulness (claims supported by their cited chunks) | 86.4% |
| Fully faithful answers | 76.0% |
| Citation accuracy (46 citations) | 97.8% |
| Factual claims with no citation | 15 |
| Latency p50 / p95 (end to end, all questions) | 6.54 s / 13.56 s |
| Cost per request | $0.000283 |

### Wrong or incomplete answers
- none

### False "I don't know"
- Why is SC 2.4.10 about section headings placed at Level AAA? (llm_said_idk, top score 9.72)

### Unsupported claims (faithfulness failures)
- How can I verify that a link’s purpose is clear after using a script to change its text? → "To verify that the link’s purpose is clear after a script changes its text, follow the steps in Technique SCR30:" cites nothing
- How can I verify that a link’s purpose is clear after using a script to change its text? → "1." cites nothing
- How can I verify that a link’s purpose is clear after using a script to change its text? → "Locate a link near the top of the page that expands other links." cites nothing
- How can I verify that a link’s purpose is clear after using a script to change its text? → "2." cites nothing
- How can I verify that a link’s purpose is clear after using a script to change its text? → "Confirm that the link can already be identified from its text alone." cites nothing
- How can I verify that a link’s purpose is clear after using a script to change its text? → "3." cites nothing
- How can I verify that a link’s purpose is clear after using a script to change its text? → "Find any links on the page whose purpose cannot be identified from the link text alone." cites nothing
- How can I verify that a link’s purpose is clear after using a script to change its text? → "4." cites nothing
- How can I verify that a link’s purpose is clear after using a script to change its text? → "Activate the expanding link (the script)." cites nothing
- How can I verify that a link’s purpose is clear after using a script to change its text? → "5." cites nothing
- How should a heading be formatted to be recognized by screen readers according to Technique T3? → "This spacing lets screen‑reader software detect the heading as a separate structural element." cites nothing
- How can I provide an alternative for time‑based media that is immediately next to the non‑text content? → "Place a link to the collated document that contains captions, audio description, or a full transcript immediately before or after the synchronized media (the no" cites nothing
