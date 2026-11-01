## Generation eval: `e8`

Settings: `{"PROVIDER": "openai", "MODEL": "gpt-6-luna", "REWRITE_MODEL": "gpt-5-nano", "RERANKER": "cross-encoder/ms-marco-MiniLM-L-6-v2", "CANDIDATES": 20, "PER_QUERY": 10, "TOP_K": 5, "MIN_SCORE": 0.0, "REWRITE_EFFORT": "low", "ANSWER_EFFORT": "low", "SKIP_REWRITE_IF_CLEAR": false, "USE_CACHE": false}` · judge: gpt-4.1-mini

| Metric | Value |
|---|---|
| **Accuracy** (correct answers + correct "I don't know", all 124 questions) | **75.8%** |
| Accuracy, partial = 0.5 | 84.3% |
| Correct on answerable (112) | 75.9% (correct 85 · partial 21 · incorrect 3 · refused 3) |
| "I don't know" accuracy | 95.2% |
| False "I don't know" (answerable refused) | 3 (0 by the score threshold) |
| Out-of-scope questions answered anyway | 3 / 12 |
| Faithfulness (claims supported by their cited chunks) | 90.9% |
| Fully faithful answers | 82.1% |
| Citation accuracy (200 citations) | 98.0% |
| Factual claims with no citation | 18 |
| Latency p50 / p95 (end to end, all questions) | 8.88 s / 12.6 s |
| Cost per request | $0.000387 |

### Wrong or incomplete answers
- **partial**: Why must text language and direction be identified for assistive technology to function properly?: The answer correctly explains the need to identify text language for assistive technologies to switch pronunciation rules, but it omits the importance of text direction and does not fully address the reason why assistive technologies need this information to function properly.
- **partial**: How can I verify that a link’s purpose is clear after using a script to change its text?: The answer correctly references the relevant success criterion and test rules but does not mention activating the control that expands the links or explicitly confirming the link's purpose from its text as the reference answer does.
- **partial**: How can an online auction be designed to comply with the no‑time‑limit requirement of Technique G5?: The system answer correctly states that Technique G5 involves allowing users to complete an activity without a time limit, but it does not mention the specific auction design details from the reference answer such as allowing only one bid per user and keeping the bidding open for a full day.
- **partial**: How is a general flash defined for WCAG 2.2 compliance?: Claim 1 is unsupported as it cites no source; claim 2 is supported but the answer misses the exact threshold detail from the source.
- **partial**: How does SC 2.5.2 allow users to cancel a click‑like activation before the pointer is released?: Claim 1 is unsupported as it cites no source; claim 2 is supported and matches the reference answer.
- **partial**: Why should a website avoid forcing a specific screen orientation?: The system answer correctly states the WCAG requirement about orientation but does not mention the reason related to users with fixed device orientations as in the reference answer.
- **partial**: What WCAG success criterion does Technique G212 address?: The answer correctly identifies the success criterion 2.5.2 Pointer Cancellation and that G212 is a sufficient technique, but it does not mention the conformance level as stated in the reference answer.
- **partial**: Why must non-text content be provided in electronic text form according to WCAG 2.2?: The answer correctly states the requirement for text alternatives and their purpose to enable conversion into other forms, but it does not explicitly mention that electronic text is presentation-neutral allowing multiple renderings as in the reference.
- **incorrect**: What is a recommended technique for clarifying the purpose of a link that uses both an image and text?: The system answer does not address combining adjacent image and text links to clarify link purpose as stated in the reference answer.
- **incorrect**: What type of captioning service is required for live audio to meet WCAG 2.2 SC 1.2.9?: The system answer does not specify the required live text caption service with a trained human operator as stated in the reference answer.
- **partial**: What happens if a plug‑in or applet blinks content for more than five seconds without a pause mechanism?: The system answer correctly states the requirement for a pause mechanism for blinking content over five seconds but does not address the user impact of distraction or inability to read other content as in the reference answer.
- **incorrect**: What contrast ratio is required for text for users with 20/40 visual acuity according to WCAG 2.2 SC 1.4.6?: The system answer does not mention the required 4.5:1 contrast ratio for users with 20/40 visual acuity as stated in the reference answer and incorrectly states the level and ratios without citing sources.

### False "I don't know"
- What qualifies a resource as a web page for WCAG 2.2 conformance? (llm_said_idk, top score 8.94)
- What does WCAG 2.2 define as a "section" in web content? (llm_said_idk, top score 6.99)
- Does SC 3.2.6 require help to be provided on PDFs downloaded from a website? (llm_said_idk, top score 9.62)

### Unsupported claims (faithfulness failures)
- How is a general flash defined for WCAG 2.2 compliance? → "A general flash is a pair of opposing changes in relative luminance of at least 10% of the maximum relative luminance (1.0), where the darker image has relative" cites nothing
- How does SC 2.5.2 allow users to cancel a click‑like activation before the pointer is released? → "For a click-like interaction, SC 2.5.2 (Level A) allows users to cancel by moving the pointer or finger away from the target before releasing it." cites nothing
- Can a web application use mouse input in addition to keyboard for the same functionality while still meeting WCAG 2.2 2.1.1? → "Yes." cites nothing
- What does Technique G219 address regarding drag interactions? → "Technique G219 addresses providing an alternative to dragging movements that operate on content, for content using technology that supports pointer input." cites nothing
- How does Technique ARIA25 make screen readers announce progress bar updates? → "Technique ARIA25 updates text in a visually hidden container with `aria-live="polite"`, which tells screen readers to announce changes to that content." cites nothing
- How do I center a div with CSS flexbox? → "The sources describe Flexbox for reflow, but do not explain how to center a div with CSS Flexbox." cites nothing
- How much does an accessibility audit cost? → "The sources do not state how much an accessibility audit costs." cites nothing
- How much does an accessibility audit cost? → "I don't know." cites [1, 2, 5]
- What contrast ratio is required for text for users with 20/40 visual acuity according to WCAG 2.2 SC 1.4.6? → "WCAG 2.2 SC 1.4.6 (Level AAA) requires a contrast ratio of at least 7:1 for text; large-scale text requires at least 4.5:1." cites nothing
- How can a script warn users 20 seconds before a time limit expires and allow them to request more time? → "For WCAG 2.2 Success Criterion 2.2.1, Level A, the warning must give users at least 20 seconds to extend the limit with a simple action, and they must be able t" cites [3]
- How can a web developer allow users to toggle diacritical marks on a page? → "A developer can provide links or controls to select the level of diacritical marks shown, such as none, limited marks, or all marks, and store the preference in" cites nothing
- Can a web page replace a drag‑and‑drop interaction with a single‑click action? → "Yes." cites nothing

### Out-of-scope questions answered anyway
- How do I center a div with CSS flexbox? → The sources describe Flexbox for reflow, but do not explain how to center a div with CSS Flexbox. I don't know. [3]
- How much does an accessibility audit cost? → The sources do not state how much an accessibility audit costs. I don't know. [1][2][5]
- What is the best colour palette for a bank website? → The sources do not identify a best color palette for a bank website. They specify contrast requirements: WCAG 2.2 Level AA Success Criterion 1.4.3 req
