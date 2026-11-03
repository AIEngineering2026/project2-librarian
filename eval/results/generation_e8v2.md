## Generation eval: `e8v2`

Settings: `{"PROVIDER": "openai", "MODEL": "gpt-6-luna", "REWRITE_MODEL": "gpt-5-nano", "RERANKER": "cross-encoder/ms-marco-MiniLM-L-6-v2", "CANDIDATES": 20, "PER_QUERY": 10, "TOP_K": 5, "MIN_SCORE": 0.0, "REWRITE_EFFORT": "low", "ANSWER_EFFORT": "low", "SKIP_REWRITE_IF_CLEAR": false, "USE_CACHE": false}` · judge: gpt-4.1-mini

| Metric | Value |
|---|---|
| **Accuracy** (correct answers + correct "I don't know", all 122 questions) | **80.3%** |
| Accuracy, partial = 0.5 | 86.9% |
| Correct on answerable (110) | 80.0% (correct 88 · partial 16 · incorrect 2 · refused 4) |
| "I don't know" accuracy | 95.1% |
| False "I don't know" (answerable refused) | 4 (0 by the score threshold) |
| Out-of-scope questions answered anyway | 2 / 12 |
| Faithfulness (claims supported by their cited chunks) | 97.1% |
| Fully faithful answers | 93.5% |
| Citation accuracy (219 citations) | 98.6% |
| Factual claims with no citation | 5 |
| Latency p50 / p95 (end to end, all questions) | 9.4 s / 12.78 s |
| Cost per request | $0.000404 |

### Wrong or incomplete answers
- **partial**: How can I verify that a link’s purpose is clear after using a script to change its text?: The system answer correctly references the relevant WCAG criterion and context requirements but does not mention activating the control that expands the links as the reference answer does.
- **partial**: How can an online auction be designed to comply with the no‑time‑limit requirement of Technique G5?: The answer correctly explains the general principle of Technique G5 but does not address the specific design of an online auction as in the reference answer.
- **partial**: What happens if a web page specifies a text color but omits a background color?: Claim 1 correctly states it is a failure because contrast cannot be evaluated, but claim 2 incorrectly states white is assumed for contrast measurement under WCAG 2.2 SC 1.4.3, which contradicts the failure condition.
- **partial**: Why should a website avoid forcing a specific screen orientation?: The system answer correctly explains the WCAG criterion about orientation locking but does not mention the key reason from the reference that some users have fixed device orientations, which is why sites must support both orientations.
- **partial**: What type of flashing content should be avoided to prevent seizures according to WCAG 2.2?: The system answer correctly states the flashing frequency limits but does not specify that the flashing content most likely to cause seizures is the one to avoid, as the reference answer emphasizes.
- **partial**: Why must non-text content be provided in electronic text form according to WCAG 2.2?: The answer correctly states the requirement for text alternatives to enable conversion to needed forms but does not explicitly mention that electronic text is presentation-neutral allowing multiple renderings as in the reference.
- **incorrect**: What is a recommended technique for clarifying the purpose of a link that uses both an image and text?: The system answer does not address combining adjacent image and text links to clarify link purpose as stated in the reference answer.
- **partial**: What qualifies a resource as a web page for WCAG 2.2 conformance?: The system answer correctly states that conformance applies to full web pages and includes variations, but it does not explicitly mention the requirement that the resource must be non-embedded within the scope of conformance as stated in the reference answer.
- **partial**: What does Technique G11 address regarding blinking content?: The answer correctly relates G11 to blinking content and 2.2.2 Pause, Stop, Hide, but it omits that G11 specifically addresses limiting blinking to less than five seconds to minimize distraction.
- **partial**: What happens if a plug‑in or applet blinks content for more than five seconds without a pause mechanism?: The answer correctly states the requirement for a pause mechanism for blinking content over five seconds but does not address the user impact of distraction or inability to read other content.
- **partial**: How can a keyboard user activate an image that acts as a link using scripting?: The system answer addresses accessible names and onclick handlers but does not mention tabindex or handling the Enter key as in the reference answer.
- **partial**: What is the main goal of WCAG 2.2 Guideline 2.2 regarding time constraints?: The system answer correctly identifies the goal of allowing users to complete tasks despite time limits, but it does not explicitly mention removing or extending time limits as the reference answer does.

### False "I don't know"
- Why must text language and direction be identified for assistive technology to function properly? (llm_said_idk, top score 4.62)
- How can an online test be calibrated to avoid timing affecting scores? (llm_said_idk, top score 7.99)
- When should a form use a single set of text instructions at the top instead of repeating format guidance for each field? (llm_said_idk, top score 7.26)
- How should the HTML be structured to provide a tooltip that appears on focus or hover and can be dismissed? (llm_said_idk, top score 8.67)

### Unsupported claims (faithfulness failures)
- Can a web application use mouse input in addition to keyboard for the same functionality while still meeting WCAG 2.2 2.1.1? → "Yes." cites nothing
- What happens if a web page specifies a text color but omits a background color? → "For contrast measurement under WCAG 2.2 Success Criterion 1.4.3 (Level AA), white is assumed when no background color is specified [2]." cites [2]
- How do I center a div with CSS flexbox? → "I don't know." cites nothing
- Can a web page replace a drag‑and‑drop interaction with a single‑click action? → "Yes." cites nothing
- What must a web page do to meet WCAG 2.2 Success Criterion 3.3.6 for error prevention at AAA level? → "WCAG 2.2 Success Criterion 3.3.6 is Level AAA." cites nothing
- How can you change a link’s background color when it receives focus and revert it when it loses focus using JavaScript? → "You can use JavaScript focus and blur event handlers to change a link’s background color on focus and restore it on blur; the sources do not provide the specifi" cites [1, 3]
- What is the best colour palette for a bank website? → "The sources do not specify a best color palette for a bank website." cites nothing

### Out-of-scope questions answered anyway
- How do I center a div with CSS flexbox? → The sources describe using CSS Flexbox to lay out and reflow content, but they do not explain how to center a div [1][2]. I don't know.
- What is the best colour palette for a bank website? → The sources do not specify a best color palette for a bank website. WCAG 2.2 Level AA Success Criterion 1.4.11 requires visual information needed to i
