# Demo questions

**Live app:** https://librarian-wcag.streamlit.app/

**Before the demo (10–15 minutes early):** open the app and ask question 1 once. If the app has gone to
sleep, Streamlit shows a "wake up" button: click it and wait 1–2 minutes. The first question after a
wake-up also loads the models, so it is slower.

**Backup if the app does not load:** run it locally with `py -m streamlit run streamlit_app.py`
(needs the `.env` file with `OPENAI_API_KEY`).

## Main demo (in order)

| # | Ask | Expected | Shows |
|---|---|---|---|
| 1 | What is the minimum contrast for normal text? *(example chip)* | 4.5:1, Level AA, SC 1.4.3, with numbered citations and the source cards on the right | Checkable citations |
| 2 | buttons too small? | 24 × 24 CSS pixels (SC 2.5.8, AA), 44 × 44 at AAA; "Show retrieved passages" lists "Searched for: target size…" | Question rewriting |
| 3 | Quel est le contraste minimum pour le texte ? | Answer in French, 4,5:1 | Other languages |
| 4 | What contrast does WCAG 3.0 require? | "I couldn't find this in the WCAG 2.2 documents" screen | Refuses instead of guessing |
| 5 | Does disabled button text need good contrast? | No, inactive controls are exempt | Exceptions |
| 6 | Which success criterion was removed in WCAG 2.2? | 4.1.1 Parsing | Precise facts |
| 7 | Click 👍 under any answer | "Thanks for the feedback!" (the vote is saved to a GitHub gist) | User feedback |

## Backups

| Instead of | Ask | Expected |
|---|---|---|
| 2 | How big should a touch target be? | 24 × 24 CSS pixels |
| 4 | What is the best pizza in Tunis? | "I don't know": stops right after the rewrite, with no search and no answer call |
| 5 | Does a logo need to meet contrast rules? | No, logos are exempt (may say the sources don't cover logos if that passage is not retrieved) |
| 6 | At 400% zoom, what width is 320 CSS pixels equivalent to? | 1280 CSS pixels |

## Known weak spots (avoid in the demo, mention if asked; see docs/postmortem.md)

- Can I use a puzzle CAPTCHA on my login page? → misses SC 3.3.8 (the passage is rarely retrieved)
- What's the difference between 1.4.3 and 1.4.6? → sometimes misses the 7:1 value
- Answers can vary slightly between runs (the OpenAI reasoning models do not support temperature 0)
