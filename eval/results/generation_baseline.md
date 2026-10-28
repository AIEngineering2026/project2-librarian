## Generation eval: `baseline`

Settings: `{"MODEL": "openai/gpt-oss-120b", "REWRITE_MODEL": "openai/gpt-oss-20b", "RERANKER": "cross-encoder/ms-marco-MiniLM-L-6-v2", "CANDIDATES": 20, "PER_QUERY": 10, "TOP_K": 5, "MIN_SCORE": 0.0, "REWRITE_EFFORT": null, "ANSWER_EFFORT": null}` · judge: openai/gpt-oss-20b

| Metric | Value |
|---|---|
| **Accuracy** (correct answers + correct "I don't know", all 30 questions) | **90.0%** |
| Accuracy, partial = 0.5 | 93.3% |
| Correct on answerable (26) | 88.5% (correct 23 · partial 2 · incorrect 0 · refused 1) |
| "I don't know" accuracy | 96.7% |
| False "I don't know" (answerable refused) | 1 (0 by the score threshold) |
| Out-of-scope questions answered anyway | 0 / 4 |
| Faithfulness (claims supported by their cited chunks) | 72.3% |
| Fully faithful answers | 52.0% |
| Citation accuracy (59 citations) | 94.9% |
| Factual claims with no citation | 10 |
| Latency p50 / p95 (end to end, all questions) | 5.48 s / 21.84 s |
| Cost per request | $0.000584 |

### Wrong or incomplete answers
- **partial**: How does Technique C17 relate to the Resize Text success criterion?: The answer adds extra detail not present in the reference, so it is not fully correct.
- **partial**: What does Technique G219 address regarding drag interactions?: The answer correctly describes what G219 addresses but omits the key fact that it is a sufficient technique for SC 2.5.7.

### False "I don't know"
- How is a general flash defined for WCAG 2.2 compliance? (llm_said_idk, top score 8.52)

### Unsupported claims (faithfulness failures)
- When should ariaNotify be used for a progress bar? → "Use ariaNotify only as a progressive‑enhancement supplement—i.e., after you’ve already provided a reliable technique such as the ARIA live region method (ARIA 2" cites nothing
- Why must text language and direction be identified for assistive technology to function properly? → "Assistive technologies need to know the language (and thus the script direction) of each passage so they can apply the correct pronunciation, voice‑language pac" cites nothing
- How can I verify that a link’s purpose is clear after using a script to change its text? → "Verify that the link’s purpose can be determined from the link text itself—or from the link text together with its programmatically‑determined context—after the" cites nothing
- How can an online auction be designed to comply with the no‑time‑limit requirement of Technique G5? → "Design the auction so that the bidding period is long (for example, open for a full day) and each bidder can submit a single bid at any time, eliminating any ne" cites nothing
- How does SC 2.5.2 allow users to cancel a click‑like activation before the pointer is released? → "This built‑in abort mechanism lets users avoid unintended clicks." cites nothing
- Why are headings crucial for screen reader users when navigating a page? → "Because headings convey the logical hierarchy of the page, they help users understand the overall organization and skip repeated blocks of information [3]." cites [3]
- Why are headings crucial for screen reader users when navigating a page? → "Screen readers announce each heading and its level, enabling users to navigate quickly from one heading to the next [4]." cites [4]
- Why are headings crucial for screen reader users when navigating a page? → "Descriptive headings also aid memory and prediction of what each section contains, benefiting users who read slowly or have limited short‑term memory [5]." cites [5]
- How does the technique verify that an undersized target has enough spacing from other targets? → "If no intersections occur, the target is considered to have sufficient spacing." cites nothing
- How can I provide an alternative for time‑based media that is immediately next to the non‑text content? → "Use Technique G58: add a link to the collated captions‑and‑audio‑description document immediately before or after the non‑text (e.g., video or audio) content, s" cites nothing
- How can I provide an alternative for time‑based media that is immediately next to the non‑text content? → "The link must point directly to the alternative for that specific synchronized media, and you should also provide a back‑link or function that returns the user " cites [2, 4]
- How can I provide an alternative for time‑based media that is immediately next to the non‑text content? → "This satisfies SC 1.2.3 Audio Description (Prerecorded) and SC 1.2.8 Media Alternative (Prerecorded) when used with G69 [1]." cites [1]
