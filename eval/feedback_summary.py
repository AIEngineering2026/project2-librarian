"""MAYA - T5. Summarise the 👍/👎 votes that the website saves in data/feedback.jsonl.

data/feedback.jsonl is git-ignored: it only exists on the computer that ran the server during the
user test. Copy it from there into data/ first.

Run from the project root:   py -m eval.feedback_summary
Writes eval/results/feedback.md (paste it into the report).
"""
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FILE = ROOT / "data" / "feedback.jsonl"
OUT = ROOT / "eval" / "results" / "feedback.md"
IDK = "i don't know"


def main():
    if not FILE.exists():
        sys.exit(f"{FILE} not found: copy it from the computer that ran the server.")
    votes = [json.loads(l) for l in open(FILE, encoding="utf-8-sig") if l.strip()]
    if not votes:
        sys.exit("no votes yet")
    up = [v for v in votes if v["helpful"]]
    down = [v for v in votes if not v["helpful"]]
    idk = [v for v in votes if v["answer"].strip().lower().startswith(IDK)]
    idk_down = [v for v in idk if not v["helpful"]]
    questions = Counter(v["question"].strip().lower() for v in votes)
    days = sorted({v["time"][:10] for v in votes if v.get("time")})

    lines = ["## User feedback (website 👍/👎)", "",
             "| | |", "|---|---|",
             f"| Votes | {len(votes)} ({len(questions)} different questions) |",
             f"| Helpful 👍 | {len(up)} ({100 * len(up) / len(votes):.0f}%) |",
             f"| Not helpful 👎 | {len(down)} ({100 * len(down) / len(votes):.0f}%) |",
             f"| Votes on \"I don't know\" answers | {len(idk)} ({len(idk_down)} of them 👎) |",
             f"| Helpful rate when the system answered | "
             f"{100 * sum(v['helpful'] for v in votes if v not in idk) / max(1, len(votes) - len(idk)):.0f}% |",
             f"| Dates | {days[0]} → {days[-1]} |" if days else "| Dates | - |",
             "", "### 👎 examples (the questions users found unhelpful)"]
    for v in down[:15]:
        lines.append(f"- **{v['question'].strip()}** → {v['answer'].strip().replace(chr(10), ' ')[:200]}")
    if not down:
        lines.append("- none")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines) + f"\n\nSaved {OUT}")


if __name__ == "__main__":
    sys.stdout.reconfigure(errors="replace")
    main()
