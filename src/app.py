"""KHADIJA: Streamlit UI. Show answer + clickable citations.

Run from the project root:  py -m streamlit run src/app.py
"""
import sys
import time
from pathlib import Path

import streamlit as st

# Make "from src.pipeline import ..." work when Streamlit runs this file directly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.pipeline import answer  # noqa: E402

st.set_page_config(page_title="The Librarian - WCAG 2.2", page_icon="📚")
st.title("📚 The Librarian - WCAG 2.2")
st.caption("Ask a question about web accessibility. Answers come only from the official "
           "W3C WCAG 2.2 documents, with sources. If the answer isn't there, it says so.")

EXAMPLES = [
    "What is the minimum contrast for normal text?",
    "What is the minimum target size in WCAG 2.2?",
    "Does an icon-only button need a text label?",
]

# Example buttons fill the question box
if "question" not in st.session_state:
    st.session_state.question = ""
cols = st.columns(len(EXAMPLES))
for col, ex in zip(cols, EXAMPLES):
    if col.button(ex, use_container_width=True):
        st.session_state.question = ex

with st.form("ask"):
    question = st.text_input("Your question", key="question",
                             placeholder="e.g. How big should a button be?")
    submitted = st.form_submit_button("Ask")

if submitted and question.strip():
    with st.spinner("Searching WCAG and writing the answer..."):
        start = time.perf_counter()
        result = answer(question.strip())
        seconds = time.perf_counter() - start

    st.subheader("Answer")
    st.write(result["answer"])

    chunks = result["chunks"]
    cited = set(result["citations"])

    if cited:
        st.subheader("Sources")
        # Numbers match the [1], [2]... in the answer
        for i, c in enumerate(chunks, start=1):
            if c["id"] in cited:
                st.markdown(f"**[{i}]** [{c['title']} - {c['section']}]({c['url']})")

    st.caption(f"⏱️ {seconds:.1f} s")

    with st.expander("See all retrieved passages"):
        for i, c in enumerate(chunks, start=1):
            score = c.get("rerank_score", 0.0)
            st.markdown(f"**[{i}] {c['title']} - {c['section']}** · score {score:.2f} · "
                        f"[link]({c['url']})")
            st.write(c["text"])
            st.divider()