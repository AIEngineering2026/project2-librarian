"""KHADIJA: run the hard test questions through the pipeline and print a summary table.
Use it to check a change quickly (e.g. after adding question rewriting).

Run from the project root:   py -m eval.try_questions
"""
import time

from src.pipeline import answer

# (question, what we expect)  --  "IDK" means it SHOULD say "I don't know"
TESTS = [
    ("My grey text on a white background looks faint, is that a problem?", "4.5:1 (SC 1.4.3)"),
    ("buttons too small?", "24x24 CSS px (SC 2.5.8)"),
    ("What contrast do large text and icons need?", "3:1 both (1.4.3 + 1.4.11)"),
    ("What's the difference between 1.4.3 and 1.4.6?", "AA 4.5:1 vs AAA 7:1"),
    ("Does disabled button text need good contrast?", "No, inactive exempt"),
    ("Does a logo need to meet contrast rules?", "No, logos exempt"),
    ("Which success criteria are new in WCAG 2.2?", "9 new SCs"),
    ("Is 4.1.1 Parsing still required?", "No, removed in 2.2"),
    ("At what width must content reflow without horizontal scrolling?", "320 CSS px (1.4.10)"),
    ("How many times per second can content flash?", "max 3 flashes / 1 s (2.3.1)"),
    ("Can I use a puzzle CAPTCHA on my login page?", "Not as only option (3.3.8)"),
    ("What contrast does WCAG 3.0 require?", "IDK"),
    ("Is WCAG legally required in Tunisia?", "IDK"),
    ("minimun constrast for txt", "4.5:1"),
    ("Quel est le contraste minimum pour le texte ?", "4.5:1 (answer in French)"),
]


def main():
    answer("warm up")  # load models first
    for i, (q, expected) in enumerate(TESTS, start=1):
        start = time.perf_counter()
        r = answer(q)
        secs = time.perf_counter() - start
        score = r["top_score"]
        print(f"\n#{i:<2} {q}")
        print(f"    expected : {expected}")
        print(f"    searched : {r['rewrite']['queries']}")
        print(f"    top score: {score:.2f}" if score is not None else "    top score: -", f"| {secs:.1f}s")
        if r["idk_reason"]:
            print(f"    answer   : I don't know  ({r['idk_reason']})")
        else:
            print(f"    answer   : {r['answer'][:220].replace(chr(10), ' ')}")
        time.sleep(1)  # stay under the free-tier rate limit


if __name__ == "__main__":
    main()