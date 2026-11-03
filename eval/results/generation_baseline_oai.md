## Generation eval: `baseline_oai`

Settings: `{"PROVIDER": "openai", "MODEL": "gpt-6-luna", "REWRITE_MODEL": "gpt-5-nano", "RERANKER": "cross-encoder/ms-marco-MiniLM-L-6-v2", "CANDIDATES": 20, "PER_QUERY": 10, "TOP_K": 5, "MIN_SCORE": 0.0, "REWRITE_EFFORT": null, "ANSWER_EFFORT": null, "SKIP_REWRITE_IF_CLEAR": false, "USE_CACHE": false}` · judge: gpt-5-mini

| Metric | Value |
|---|---|
| **Accuracy** (correct answers + correct "I don't know", all 124 questions) | **81.5%** |
| Accuracy, partial = 0.5 | 83.1% |
| Correct on answerable (112) | 79.5% (correct 89 · partial 4 · incorrect 8 · refused 11) |
| "I don't know" accuracy | 91.1% |
| False "I don't know" (answerable refused) | 11 (0 by the score threshold) |
| Out-of-scope questions answered anyway | 0 / 12 |
| Faithfulness (claims supported by their cited chunks) | 96.2% |
| Fully faithful answers | 92.1% |
| Citation accuracy (201 citations) | 98.0% |
| Factual claims with no citation | 6 |
| Latency p50 / p95 (end to end, all questions) | 14.77 s / 21.57 s |
| Cost per request | $0.000989 |

### Wrong or incomplete answers
- **partial**: What technique can I use to allow users to skip a block of repeated content on a page?: The answer correctly gives the recommended link technique but adds an additional technique (expand/collapse menu) not present in the reference.
- **partial**: What type of flashing content should be avoided to prevent seizures according to WCAG 2.2?: Claim 1 misstated the relationship between flash count and area (they are alternative thresholds, not both required), while Claim 2 correctly cites the fine-pattern exception.
- **incorrect**: What is a recommended technique for clarifying the purpose of a link that uses both an image and text?: The reference specifically recommends combining adjacent image and text links to point to the same resource; the system answer gives a general guideline about link text and context but does not state the combining technique.
- **incorrect**: What contrast ratio is required for text for users with 20/40 visual acuity according to WCAG 2.2 SC 1.4.6?: The system answer states 7:1 for text (4.5:1 only for large text), but the reference answer identifies 4.5:1 as the required ratio for users with 20/40 acuity.
- **incorrect**: How can a keyboard user activate an image that acts as a link using scripting?: The reference answer specifies adding a tabindex and handling the Enter key with onkeypress, which the system answer does not mention.
- **partial**: Can a web page replace a drag‑and‑drop interaction with a single‑click action?: The answer correctly states that dragging functionality must have a single-pointer alternative and gives appropriate examples, but it omits the exception about drags that are essential (and only notes the user-agent exception indirectly).
- **incorrect**: How can an online test be calibrated to avoid timing affecting scores?: The system answer describes WCAG 2.2 Timing Adjustable details rather than the reference guidance about calibrating tests using no-time-limit scores.
- **incorrect**: What qualifies a collection of web pages as a "set" according to WCAG 2.2?: The answer describes what a conformance claim can cover but does not state the definition of a “set” (common purpose and same author) given in the reference.
- **incorrect**: How can I inform users about a context change before a form control updates?: The reference answer specifies technique G13; the system answer omits this required technique.
- **incorrect**: When should a form use a single set of text instructions at the top instead of repeating format guidance for each field?: The system answer does not state the conditions from the reference (few fields or many fields share the same format), instead only repeating what the source says about the technique and that it lacks guidance on when to replace per-field instructions.
- **partial**: What contrast ratio is required for visual cues that identify a control and its state in UI components?: The answer correctly gives the 3:1 contrast requirement but says 'against the background' rather than the reference's 'with adjacent colors.'
- **incorrect**: How can a social security number input be grouped for accessibility?: The reference answer specifies using role=group, but the system answer recommends fieldset/legend (H71) instead.

### False "I don't know"
- Why must text language and direction be identified for assistive technology to function properly? (llm_said_idk, top score 7.95)
- How is a general flash defined for WCAG 2.2 compliance? (llm_said_idk, top score 7.0)
- How does SC 2.5.2 allow users to cancel a click‑like activation before the pointer is released? (llm_said_idk, top score 9.4)
- What type of captioning service is required for live audio to meet WCAG 2.2 SC 1.2.9? (llm_said_idk, top score 7.54)
- What qualifies a resource as a web page for WCAG 2.2 conformance? (llm_said_idk, top score 7.46)
- Why should developers avoid fully justified text for users with cognitive disabilities? (llm_said_idk, top score 8.09)
- What happens if only the foreground color is set in CSS and the background color is omitted? (llm_said_idk, top score 8.06)
- How can a web developer allow users to toggle diacritical marks on a page? (llm_said_idk, top score 7.7)
- What WCAG 2.2 success criteria can be violated when a script removes focus immediately after it is received? (llm_said_idk, top score 8.92)
- How can you change a link’s background color when it receives focus and revert it when it loses focus using JavaScript? (llm_said_idk, top score 9.16)
- Does SC 3.2.6 require help to be provided on PDFs downloaded from a website? (llm_said_idk, top score 9.09)

### Unsupported claims (faithfulness failures)
- Can a web application use mouse input in addition to keyboard for the same functionality while still meeting WCAG 2.2 2.1.1? → "Yes." cites nothing
- What type of flashing content should be avoided to prevent seizures according to WCAG 2.2? → "Under WCAG 2.2 Level A, Success Criterion 2.3.1, avoid flashing content that exceeds the flash thresholds: more than three general or red flashes in any one-sec" cites [1, 5]
- How does Technique ARIA25 make screen readers announce progress bar updates? → "ARIA25 updates text in a visually hidden container with `aria-live="polite"`, which tells screen readers to announce changes to that content." cites nothing
- Can a web page replace a drag‑and‑drop interaction with a single‑click action? → "Yes." cites nothing
- How can I inform users about a context change before a form control updates? → "The sources do not specify how to provide that advice." cites [3]
- Are WCAG 2 techniques mandatory for conformance? → "No." cites nothing
- What does the WCAG glossary define as a "user interface component"? → "A “user interface component” is a part of content that users perceive as a single control for a distinct function." cites nothing
- Can content that requires path-dependent input conform to SC 2.1.3 Keyboard (No Exception)? → "No." cites nothing
