"""
Step 3: take a question, get the matching WCAG rules, and ask the AI to answer
using ONLY those rules, with a citation for each fact.
"""

import os
from dotenv import load_dotenv
from groq import Groq

from fake_retrieve import retrieve  # later: swap for Mayssa's real retrieve()

load_dotenv()  # reads GROQ_API_KEY from the .env file
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

MODEL = "openai/gpt-oss-120b"

SYSTEM_PROMPT = """You are a WCAG 2.2 accessibility assistant.
Rules:
1. Answer ONLY using the sources given to you. Never use outside knowledge.
2. After every fact, cite its source like [SC 1.4.3].
3. If the sources do not contain the answer, reply exactly: I don't know.
4. Keep the answer short and clear."""


def build_sources_text(chunks):
    """Turn the chunks into one block of text the AI can read."""
    parts = []
    for c in chunks:
        parts.append(f"[SC {c['section']}] {c['title']}\n{c['text']}")
    return "\n\n".join(parts)


def answer(question, k=3):
    chunks = retrieve(question, k)
    sources = build_sources_text(chunks)

    response = client.chat.completions.create(
        model=MODEL,
        temperature=0,  # 0 = same question gives the same answer (good for testing)
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Sources:\n{sources}\n\nQuestion: {question}"},
        ],
    )
    text = response.choices[0].message.content
    return {"answer": text, "sources": chunks}


if __name__ == "__main__":
    question = "What is the minimum contrast for normal text?"
    result = answer(question)
    print("Q:", question)
    print("A:", result["answer"])
    print("\nSources used:")
    for c in result["sources"]:
        print(" -", c["section"], c["url"])