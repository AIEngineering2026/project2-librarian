"""Check which OpenAI models support what our pipeline needs (tiny calls, a fraction of a cent).

For each candidate model it tests:
  - a plain call
  - reasoning_effort = "low" and "minimal"  (our Week 8 optimisation)
  - temperature = 0                         (deterministic answers)

Put the key in .env as   OPENAI_API_KEY=sk-...   then run from the project root:
    py -m eval.check_openai
"""
import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

CANDIDATES = ["gpt-5-nano", "gpt-5-mini", "gpt-6-luna", "gpt-4.1-mini"]
TESTS = {
    "plain": {},
    "effort=low": {"reasoning_effort": "low"},
    "effort=minimal": {"reasoning_effort": "minimal"},
    "temperature=0": {"temperature": 0},
}
MESSAGES = [{"role": "user", "content": "Reply with exactly: OK"}]

available = {m.id for m in client.models.list()}
print(f"{'model':14} " + " ".join(f"{t:>16}" for t in TESTS))
for model in CANDIDATES:
    if model not in available:
        print(f"{model:14} not available")
        continue
    cells = []
    for name, extra in TESTS.items():
        try:
            r = client.chat.completions.create(model=model, messages=MESSAGES, **extra)
            cells.append(f"OK ({r.usage.completion_tokens} out)")
        except Exception as e:
            cells.append("NOT SUPPORTED" if "support" in str(e).lower() or "unsupported" in str(e).lower()
                         else "ERROR")
    print(f"{model:14} " + " ".join(f"{c:>16}" for c in cells))