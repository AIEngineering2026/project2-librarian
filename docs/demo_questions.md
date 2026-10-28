# Demo questions

Start: `py -m uvicorn src.server:app` → open http://127.0.0.1:8000 → ask question 1 once as a warm-up
(the first answer loads the models). Each question uses ≈ 1,500 Groq tokens.

## Main demo (in order)

| # | Ask | Expected | Shows |
|---|---|---|---|
| 1 | What is the minimum contrast for normal text? *(chip)* | 4.5:1, Level AA, SC 1.4.3. Hover `[1]` → source lights up | Checkable citations |
| 2 | buttons too small? | 24 × 24 CSS pixels, SC 2.5.8; passages show "Searched for: target size" | Question rewriting |
| 3 | Quel est le contraste minimum pour le texte ? | Answer in French, 4,5:1 | Other languages |
| 4 | What contrast does WCAG 3.0 require? | "I couldn't find this" screen | Refuses instead of guessing |
| 5 | Does disabled button text need good contrast? | No, inactive controls are exempt | Exceptions |
| 6 | Which success criterion was removed in WCAG 2.2? | 4.1.1 Parsing | Precise facts |
| 7 | Click 👍 on any answer | "Thanks for the feedback!" | User feedback |

## Backups

| Instead of | Ask | Expected |
|---|---|---|
| 2 | How big should a touch target be? | 24 × 24 CSS pixels |
| 4 | What is the best pizza in Tunis? | "I don't know" (stops before the LLM, free) |
| 5 | Does a logo need to meet contrast rules? | No, logos are exempt |
| 6 | At 400% zoom, what width is 320 CSS pixels equivalent to? | 1280 CSS pixels |

## Known weak spots (avoid in the demo, mention if asked; see docs/postmortem.md)

- Can I use a puzzle CAPTCHA on my login page? → misses SC 3.3.8
- How many times per second can content flash? → cites 2.3.2 (AAA) instead of 2.3.1
- What does reflow mean in WCAG? / Why is SC 2.4.10 Level AAA? → wrong "I don't know"