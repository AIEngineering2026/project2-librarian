## Generation eval: `baseline_mini`

Settings: `{"PROVIDER": "openai", "MODEL": "gpt-5-mini", "REWRITE_MODEL": "gpt-5-nano", "RERANKER": "cross-encoder/ms-marco-MiniLM-L-6-v2", "CANDIDATES": 20, "PER_QUERY": 10, "TOP_K": 5, "MIN_SCORE": 0.0, "REWRITE_EFFORT": null, "ANSWER_EFFORT": null, "SKIP_REWRITE_IF_CLEAR": false, "USE_CACHE": false}` · judge: gpt-4.1-mini

| Metric | Value |
|---|---|
| **Accuracy** (correct answers + correct "I don't know", all 124 questions) | **74.2%** |
| Accuracy, partial = 0.5 | 79.4% |
| Correct on answerable (112) | 72.3% (correct 81 · partial 13 · incorrect 2 · refused 16) |
| "I don't know" accuracy | 86.3% |
| False "I don't know" (answerable refused) | 16 (0 by the score threshold) |
| Out-of-scope questions answered anyway | 1 / 12 |
| Faithfulness (claims supported by their cited chunks) | 98.5% |
| Fully faithful answers | 95.9% |
| Citation accuracy (331 citations) | 99.1% |
| Factual claims with no citation | 2 |
| Latency p50 / p95 (end to end, all questions) | 24.68 s / 34.67 s |
| Cost per request | $0.003208 |

### Wrong or incomplete answers
- **partial**: How can I verify that a link’s purpose is clear after using a script to change its text?: The answer explains relevant success criteria and test rules but does not explicitly mention activating controls to expand links or confirming purpose from text alone as the reference answer does.
- **partial**: How can I provide an alternative for time‑based media that is immediately next to the non‑text content?: The answer correctly states placing a link immediately adjacent to the media but adds unnecessary detail about the collated document and level AAA not in the reference.
- **partial**: How does Technique C17 relate to the Resize Text success criterion?: Claim 3 incorrectly states that C17 is sufficient when combined with other techniques, but the source states this about C28, not C17.
- **partial**: What happens if a web page specifies a text color but omits a background color?: The answer correctly states it is a failure because contrast cannot be evaluated, but incorrectly claims white is assumed as background color.
- **partial**: Why must non-text content be provided in electronic text form according to WCAG 2.2?: The answer correctly states the requirement for text alternatives to enable content transformation into other forms but does not explicitly mention that electronic text is presentation-neutral and can be rendered visually, audibly, tactilely, or in combination as in the reference.
- **incorrect**: What type of captioning service is required for live audio to meet WCAG 2.2 SC 1.2.9?: The system answer does not specify the required live text caption service with a trained human operator as stated in the reference answer.
- **partial**: What qualifies a resource as a web page for WCAG 2.2 conformance?: The system answer explains conformance scope and full page variations but does not explicitly state that a resource must be non-embedded to qualify as a web page, which is the key point in the reference answer.
- **incorrect**: What contrast ratio is required for text for users with 20/40 visual acuity according to WCAG 2.2 SC 1.4.6?: The system answer gives contrast ratios for normal and large-scale text but does not mention the 4.5:1 ratio specifically for users with 20/40 visual acuity as stated in the reference.
- **partial**: How can an online test be calibrated to avoid timing affecting scores?: The system answer focuses on pausing or stopping auto-updating content but does not mention calibrating the test based on scores without time limits as the reference answer states.
- **partial**: What qualifies a collection of web pages as a "set" according to WCAG 2.2?: The system answer explains what a set can be in terms of conformance claims and processes but does not mention the key aspect of sharing a common purpose and being created by the same author, group, or organization as stated in the reference.
- **partial**: What are two common failure types for SC 1.2.1 regarding audio-only and video-only content?: The system answer correctly describes failures related to missing alternatives for audio-only and video-only content but does not identify the specific common failure types F30 and F67 as in the reference.
- **partial**: How can a control slider be made operable for users who cannot perform path-based gestures?: The answer correctly references the need for a single-pointer non-path-based alternative but does not explicitly mention making the slider track clickable or adding arrow buttons as in the reference answer.

### False "I don't know"
- Why must text language and direction be identified for assistive technology to function properly? (llm_said_idk, top score 7.36)
- How can an online auction be designed to comply with the no‑time‑limit requirement of Technique G5? (llm_said_idk, top score 8.51)
- How does Technique G112 help with the 3.1.3 Unusual Words criterion? (llm_said_idk, top score 7.94)
- At 400% zoom, what starting viewport width is 320 CSS pixels equivalent to (SC 1.4.10 Reflow)? (llm_said_idk, top score 8.8)
- What does Technique G219 address regarding drag interactions? (llm_said_idk, top score 7.63)
- What does Technique G11 address regarding blinking content? (llm_said_idk, top score 9.27)
- Why should developers avoid fully justified text for users with cognitive disabilities? (llm_said_idk, top score 7.7)
- What happens if only the foreground color is set in CSS and the background color is omitted? (llm_said_idk, top score 8.07)
- How does Technique G142 ensure that zooming preserves spatial relationships and functionality? (llm_said_idk, top score 7.82)
- How can a keyboard user activate an image that acts as a link using scripting? (llm_said_idk, top score 6.19)
- What must be done when a CAPTCHA is used to confirm human access? (llm_said_idk, top score 8.22)
- How can a web developer allow users to toggle diacritical marks on a page? (llm_said_idk, top score 8.02)

### Unsupported claims (faithfulness failures)
- How does Technique C17 relate to the Resize Text success criterion? → "Technique C17 is documented as a technique that can be sufficient when combined with other techniques to meet Success Criterion 1.4.4 Resize Text [3]." cites [3]
- What happens if a web page specifies a text color but omits a background color? → "If no background color is specified, white is assumed [4]." cites [4]
- How should a developer cite a WCAG 2.2 technique from a support document? → "References to techniques should be cited separately by citing the individual Technique document or the master WCAG 2.2 Techniques document, for example: "Using " cites nothing
- How can you change a link’s background color when it receives focus and revert it when it loses focus using JavaScript? → "You can use JavaScript to toggle the link’s background on focus and blur, for example: function toggleFocus(el) { el.style.backgroundColor = el.style.background" cites nothing

### Out-of-scope questions answered anyway
- What is the best colour palette for a bank website? → Level AA — Success Criterion 1.4.11 Non-text Contrast: ensure meaningful visual cues achieve 3:1 against the background [1].  
Level AA — Success Crit
