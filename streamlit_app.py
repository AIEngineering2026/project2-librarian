"""KHADIJA: The Librarian on Streamlit Community Cloud. Same design as web/index.html.

Run locally:   py -m streamlit run streamlit_app.py
On the cloud:  Streamlit Community Cloud runs this file. Secrets (Settings -> Secrets):
    OPENAI_API_KEY = "sk-..."
    GITHUB_TOKEN   = "..."   # optional: a token with only the "gist" permission
    GIST_ID        = "..."   # optional: the secret gist where votes are kept

Votes are written to data/feedback.jsonl AND, if the two optional secrets are set, to a GitHub gist,
because Streamlit Cloud deletes local files when the app restarts.
"""
import html
import json
import os
import re
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

# The key must be in the environment BEFORE the pipeline is imported (it creates the OpenAI client).
for name in ("OPENAI_API_KEY", "LLM_PROVIDER", "ANSWER_MODEL", "REWRITE_MODEL"):
    try:
        if name in st.secrets:
            os.environ[name] = st.secrets[name]
    except Exception:   # no secrets file when running locally: .env is used instead
        pass

from src import pipeline                       # noqa: E402
from src.retrieve import retrieve              # noqa: E402
from eval.latency_cost import cost_usd         # noqa: E402

FEEDBACK_FILE = Path("data/feedback.jsonl")
GIST_FILE = "feedback.jsonl"
GITHUB_URL = "https://github.com/AIEngineering2026/project2-librarian"
SC_RE = re.compile(r"\b([1-4])\.(\d{1,2})\.(\d{1,2})\b")
PRINCIPLES = {"1": "Perceivable", "2": "Operable", "3": "Understandable", "4": "Robust"}
STYLE = {  # colour, background, border per WCAG principle (same as web/index.html)
    "Perceivable": ("#1D4ED8", "#EFF4FF", "#BFDBFE"), "Operable": ("#6D28D9", "#F5F3FF", "#DDD6FE"),
    "Understandable": ("#0F766E", "#F0FDFA", "#99F6E4"), "Robust": ("#B45309", "#FFFBEB", "#FDE68A"),
    None: ("#475569", "#F1F5F9", "#E2E8F0"),
}
EXAMPLES = [("1.4.3", "What is the minimum contrast for normal text?"),
            ("2.5.8", "What is the minimum target size in WCAG 2.2?"),
            ("3.3.2", "Do form inputs need visible labels?"),
            ("4.1.2", "Does an icon-only button need a label?")]
IDK_TEXT = {
    "off_topic": "This question doesn't seem to be about web accessibility.",
    "low_score": "No passage in the WCAG 2.2 documents matches this question.",
    "llm_said_idk": "The passages found don't answer this question, so it won't guess.",
}

st.set_page_config(page_title="The Librarian · WCAG 2.2 Assistant", page_icon="📘", layout="wide",
                   initial_sidebar_state="collapsed")


def h(s):
    """Join an HTML snippet into one line (Streamlit's markdown breaks on blank or indented lines)."""
    return " ".join(line.strip() for line in s.splitlines() if line.strip())



def icon(name, size=20, color="currentColor"):
    """Small inline SVG icons (always display, no icon font needed)."""
    paths = {
        "book": "M21 5c-1.1-.35-2.3-.5-3.5-.5-1.95 0-4.05.4-5.5 1.5-1.45-1.1-3.55-1.5-5.5-1.5S2.45 4.9 1 6v14.65c0 .25.25.5.5.5.1 0 .15-.05.25-.05C3.1 20.45 5.05 20 6.5 20c1.95 0 4.05.4 5.5 1.5 1.35-.85 3.8-1.5 5.5-1.5 1.65 0 3.35.3 4.75 1.05.1.05.15.05.25.05.25 0 .5-.25.5-.5V6c-.6-.45-1.25-.75-2-1zm0 13.5c-1.1-.35-2.3-.5-3.5-.5-1.7 0-4.15.65-5.5 1.5V8c1.35-.85 3.8-1.5 5.5-1.5 1.2 0 2.4.15 3.5.5v11.5z",
        "shield": "M12 1 3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-4zm-2 16-4-4 1.41-1.41L10 14.17l6.59-6.59L18 9l-8 8z",
        "quote": "M6 17h3l2-4V7H5v6h3zm8 0h3l2-4V7h-6v6h3z",
        "help": "M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 17h-2v-2h2v2zm2.07-7.75-.9.92C13.45 12.9 13 13.5 13 15h-2v-.5c0-1.1.45-2.1 1.17-2.83l1.24-1.26c.37-.36.59-.86.59-1.41 0-1.1-.9-2-2-2s-2 .9-2 2H8c0-2.21 1.79-4 4-4s4 1.79 4 4c0 .88-.36 1.68-.93 2.25z",
        "timer": "M15 1H9v2h6V1zm-4 13h2V8h-2v6zm8.03-6.61 1.42-1.42c-.43-.51-.9-.99-1.41-1.41l-1.42 1.42C16.07 4.74 14.12 4 12 4c-4.97 0-9 4.03-9 9s4.02 9 9 9 9-4.03 9-9c0-2.12-.74-4.07-1.97-5.61zM12 20c-3.87 0-7-3.13-7-7s3.13-7 7-7 7 3.13 7 7-3.13 7-7 7z",
    }
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="{color}" aria-hidden="true" '
            f'style="vertical-align:middle"><path d="{paths[name]}"/></svg>')

def principle_of(sc):
    return PRINCIPLES.get(sc[0]) if sc else None


def sc_pill(sc):
    c, bg, b = STYLE[principle_of(sc)]
    return f'<span class="scpill" style="color:{c};background:{bg};border-color:{b}">SC {sc}</span>'


# ---------- styles (colours, fonts and shapes from web/index.html) ----------
chip_css = ""
for i, (sc, _) in enumerate(EXAMPLES):
    c, bg, b = STYLE[principle_of(sc)]
    chip_css += (f".st-key-chip{i} button, .st-key-idkchip{i} button {{color:{c} !important;background:{bg} !important;"
                 f"border:1px solid {b} !important;}}\n")

st.markdown(f"""<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500;600;700&display=swap');
:root {{ --blue:#1D4ED8; --violet:#7C3AED; --teal:#0F766E; }}
.stApp, .stApp p, .stApp input, .stApp button, .stMarkdown {{ font-family:'Inter',sans-serif; }}
.ms {{ font-family:'Material Symbols Outlined'; font-weight:normal; font-style:normal; line-height:1; vertical-align:middle;
       font-variation-settings:'FILL' 1; display:inline-block; }}
#MainMenu, header[data-testid="stHeader"], footer, [data-testid="stToolbar"], [data-testid="stSidebar"],
[data-testid="collapsedControl"], [data-testid="stDecoration"] {{ display:none !important; }}
.stApp {{ background:linear-gradient(135deg,#EFF4FF 0%,#F6F2FF 50%,#E8FBF4 100%); }}
.block-container {{ max-width:1080px; padding-top:6.5rem; padding-bottom:0; }}
.blob {{ position:fixed; border-radius:50%; filter:blur(64px); z-index:0; pointer-events:none; animation:drift 18s ease-in-out infinite alternate; }}
@keyframes drift {{ to {{ transform:translate(40px,30px) scale(1.08); }} }}
@media (prefers-reduced-motion: reduce) {{ *,*::before,*::after {{ animation:none !important; transition:none !important; }} }}

.nav {{ position:fixed; top:0; left:0; right:0; z-index:999; height:64px; background:rgba(255,255,255,.75);
        backdrop-filter:blur(12px); border-bottom:1px solid rgba(226,232,240,.7); }}
.nav-in {{ max-width:1080px; margin:0 auto; height:64px; padding:0 24px; display:flex; align-items:center; justify-content:space-between; }}
.logo {{ display:flex; align-items:center; gap:12px; text-decoration:none !important; color:#0F172A !important; }}
.logo-ic {{ width:36px; height:36px; border-radius:12px; background:linear-gradient(135deg,var(--blue),var(--violet));
            display:flex; align-items:center; justify-content:center; color:#fff; font-size:20px; box-shadow:0 4px 10px rgba(59,130,246,.25); }}
.logo b {{ font-size:18px; font-weight:700; letter-spacing:-.01em; }}
.tag {{ font:600 11px 'JetBrains Mono',monospace; padding:2px 8px; border-radius:999px; background:#EFF6FF; color:var(--blue); border:1px solid #BFDBFE; }}
.nav-links a {{ margin-left:24px; font-size:14px; font-weight:500; color:#475569 !important; text-decoration:none !important; }}
.nav-links a:hover {{ color:var(--blue) !important; }}

.hero {{ text-align:center; max-width:760px; margin:0 auto; }}
.hero .h1 {{ font-size:48px; font-weight:800; letter-spacing:-.025em; line-height:1.12; color:#0F172A; }}
.hero .h1 span {{ background:linear-gradient(90deg,var(--blue),var(--violet),var(--teal)); -webkit-background-clip:text;
                  background-clip:text; color:transparent; }}
.hero p {{ margin-top:16px; font-size:18px; color:#475569; line-height:1.6; }}

.st-key-askbox {{ max-width:680px; margin:28px auto 0; background:rgba(255,255,255,.95); border:1px solid #E2E8F0;
                  border-radius:16px; padding:8px 8px 8px 14px; box-shadow:0 10px 24px rgba(30,58,138,.06); }}
.st-key-askbox [data-testid="stForm"] {{ border:none; padding:0; }}
.st-key-askbox input {{ background:transparent !important; font-size:16px !important; border:none !important; }}
.st-key-askbox [data-baseweb="input"], .st-key-askbox [data-baseweb="base-input"] {{ background:transparent !important; border:none !important; }}
.st-key-askbox button {{ height:44px; border:none !important; border-radius:12px !important; color:#fff !important; font-weight:600 !important;
                         background:linear-gradient(90deg,var(--blue),var(--violet)) !important; box-shadow:0 4px 10px rgba(37,99,235,.25); }}
.st-key-askbox button:hover {{ filter:brightness(1.1); }}

.st-key-chips {{ max-width:900px; margin:16px auto 0; }}
[class*="st-key-chip"] button, [class*="st-key-idkchip"] button {{ border-radius:999px !important; font-size:13px !important;
    font-weight:500 !important; min-height:0 !important; padding:6px 14px !important; transition:all .15s; }}
[class*="st-key-chip"] button p, [class*="st-key-idkchip"] button p {{ white-space:normal !important; text-align:center; }}
[class*="st-key-chip"] button:hover, [class*="st-key-idkchip"] button:hover {{ transform:translateY(-2px); box-shadow:0 2px 6px rgba(15,23,42,.1); }}
{chip_css}
.cards {{ display:grid; grid-template-columns:repeat(3,1fr); gap:20px; margin-top:48px; }}
@media (max-width:800px) {{ .cards {{ grid-template-columns:1fr; }} .hero .h1 {{ font-size:36px; }} }}
.fcard {{ background:rgba(255,255,255,.9); border:1px solid rgba(226,232,240,.8); border-radius:16px; padding:24px;
          transition:all .2s; }}
.fcard:hover {{ transform:translateY(-4px); box-shadow:0 12px 28px rgba(15,23,42,.08); }}
.fcard .ic {{ display:inline-flex; padding:12px; border-radius:12px; font-size:22px; }}
.fcard h3 {{ margin:16px 0 0; font-size:18px; font-weight:700; color:#0F172A; padding:0; }}
.fcard p {{ margin-top:8px; font-size:14px; color:#475569; line-height:1.6; }}
.fcard .ft {{ margin-top:20px; padding-top:16px; border-top:1px solid #F1F5F9; font:600 11px 'JetBrains Mono',monospace; }}

.acard {{ background:rgba(255,255,255,.95); border:1px solid rgba(226,232,240,.7); border-left:4px solid var(--blue);
          border-radius:16px; padding:28px 30px 18px; box-shadow:0 6px 20px rgba(15,23,42,.06); animation:fadeUp .45s ease-out both; }}
@keyframes fadeUp {{ from {{ opacity:0; transform:translateY(10px); }} to {{ opacity:1; transform:none; }} }}
.ahead {{ display:flex; flex-wrap:wrap; align-items:center; justify-content:space-between; gap:10px; padding-bottom:16px;
          margin-bottom:18px; border-bottom:1px solid #F1F5F9; }}
.ahead .l {{ display:flex; align-items:center; gap:10px; }}
.dot {{ width:10px; height:10px; border-radius:50%; background:#10B981; box-shadow:0 0 0 4px rgba(16,185,129,.15); }}
.ahead h4 {{ margin:0; padding:0; font-size:18px; font-weight:600; color:#0F172A; }}
.grounded {{ font:600 11px 'JetBrains Mono',monospace; padding:2px 8px; border-radius:999px; background:#ECFDF5; color:#047857; border:1px solid #A7F3D0; }}
.lat {{ font:12px 'JetBrains Mono',monospace; color:#64748B; display:flex; align-items:center; gap:6px; }}
.atext {{ font-size:16px; line-height:1.7; color:#1E293B; }}
.cite {{ font:700 11px 'JetBrains Mono',monospace; color:var(--blue); background:#EFF4FF; border:1px solid #BFDBFE;
         border-radius:999px; padding:3px 7px; margin-left:3px; vertical-align:2px; }}
.scpill {{ font:600 .8em 'JetBrains Mono',monospace; border-radius:6px; padding:1px 6px; border:1px solid; white-space:nowrap; }}
.qline {{ font-size:14px; color:#64748B; margin-bottom:6px; }}
.qline b {{ color:#0F172A; }}

.scard {{ background:rgba(255,255,255,.95); border:1px solid rgba(226,232,240,.7); border-radius:16px; padding:18px 20px;
          box-shadow:0 6px 20px rgba(15,23,42,.06); animation:fadeUp .45s .08s ease-out both; }}
.shead {{ display:flex; justify-content:space-between; padding-bottom:12px; margin-bottom:14px; border-bottom:1px solid #F1F5F9;
          font:700 11px 'JetBrains Mono',monospace; letter-spacing:.06em; color:#475569; }}
.src {{ display:flex; gap:12px; padding:12px; border-radius:12px; background:#F8FAFC; border:1px solid #F1F5F9; margin-bottom:10px; }}
.src .n {{ font:700 12px 'JetBrains Mono',monospace; color:var(--blue); background:#EFF4FF; border:1px solid #BFDBFE;
           border-radius:999px; height:22px; min-width:22px; display:flex; align-items:center; justify-content:center; }}
.src .t {{ font-size:14px; font-weight:600; color:#0F172A; line-height:1.4; }}
.src .s {{ font-size:12.5px; color:#64748B; margin-top:3px; }}
.src a {{ font-size:12.5px; font-weight:600; color:var(--blue) !important; text-decoration:none !important; }}

.searched {{ display:flex; flex-wrap:wrap; align-items:center; gap:8px; font-size:13px; color:#64748B; margin-bottom:8px; }}
.qchip {{ background:#F5F3FF; color:#6D28D9; border:1px solid #DDD6FE; border-radius:999px; padding:3px 10px; font-size:12.5px; }}
.passage {{ border:1px solid #F1F5F9; background:#F8FAFC; border-radius:12px; padding:12px 14px; margin-bottom:10px; font-size:14px; color:#334155; line-height:1.6; }}
.passage .ph {{ font-weight:600; color:#0F172A; margin-bottom:4px; }}
.st-key-votes {{ margin-top:-4px; }}
.st-key-votes button {{ border-radius:10px !important; background:#F1F5F9 !important; border:none !important; }}
.thanks {{ font:600 11px 'JetBrains Mono',monospace; color:#047857; }}

.idk {{ position:relative; overflow:hidden; max-width:680px; margin:40px auto 0; text-align:center; background:rgba(255,255,255,.95);
        border:1px solid rgba(253,230,138,.7); border-radius:16px; padding:40px 36px 30px; box-shadow:0 4px 24px -4px rgba(245,158,11,.10);
        animation:fadeUp .45s ease-out both; }}
.idk h3 {{ margin-top:18px; font-size:24px; font-weight:700; color:#0F172A; padding:0; }}
.idk p {{ margin-top:10px; font-size:15px; color:#475569; line-height:1.6; }}
.idk .or {{ margin-top:22px; font-size:12px; font-weight:600; letter-spacing:.08em; color:#64748B; }}
.st-key-idkchips {{ max-width:680px; margin:10px auto 0; }}
.foot {{ margin-top:64px; border-top:1px solid rgba(226,232,240,.7); padding:24px; text-align:center;
         font:12px 'JetBrains Mono',monospace; color:#64748B; }}
.about {{ max-width:680px; margin:40px auto 0; background:rgba(255,255,255,.9); border:1px solid #E2E8F0; border-radius:16px; padding:24px 28px; }}
.about h3 {{ font-size:20px; font-weight:700; margin:0; padding:0; color:#0F172A; }}
.about p, .about li {{ font-size:14px; color:#475569; line-height:1.6; }}
.about ol {{ list-style:none; padding:0; margin:12px 0 0; }}
.about li {{ display:flex; gap:12px; margin-top:6px; color:#334155; }}
.about li b {{ font-family:'JetBrains Mono',monospace; }}
.warn {{ margin-top:16px; padding:10px 12px; border-radius:12px; background:#FFFBEB; border:1px solid #FDE68A; font-size:13px; color:#78350F; }}
</style>""", unsafe_allow_html=True)

st.markdown(h("""
<div class="blob" style="top:-96px;left:12%;width:480px;height:380px;background:rgba(147,197,253,.30)"></div>
<div class="blob" style="top:40px;right:10%;width:440px;height:360px;background:rgba(196,181,253,.25);animation-duration:22s"></div>
<div class="blob" style="top:300px;left:38%;width:520px;height:320px;background:rgba(167,243,208,.40)"></div>
<div class="nav"><div class="nav-in">
  <a class="logo" href="./" target="_self"><span class="logo-ic">""" + icon("book", 20, "#fff") + """</span><b>The Librarian</b><span class="tag">WCAG 2.2</span></a>
  <div class="nav-links"><a href="#about" target="_self">About</a><a href="""
            + f'"{GITHUB_URL}"' + """ target="_blank">GitHub</a></div>
</div></div>
"""), unsafe_allow_html=True)


# ---------- logic ----------
@st.cache_resource(show_spinner="Loading the search index and models (the first start can take a few minutes)...")
def warm_up():
    """Load (or build) the index and the reranker once per server, not once per visitor."""
    retrieve("warm up", k=1)
    pipeline.get_reranker()
    return True


def secret(name):
    try:
        return st.secrets.get(name)
    except Exception:
        return None


def save_vote(row):
    """Append the vote to the local file, then to the gist (if configured)."""
    line = json.dumps(row, ensure_ascii=False)
    FEEDBACK_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(FEEDBACK_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")
    token, gist_id = secret("GITHUB_TOKEN"), secret("GIST_ID")
    if not (token and gist_id):
        return
    url = f"https://api.github.com/gists/{gist_id}"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=10) as r:
            current = json.load(r)["files"].get(GIST_FILE, {}).get("content", "")
        body = json.dumps({"files": {GIST_FILE: {"content": current.rstrip("\n") + "\n" + line + "\n"}}}).encode()
        urllib.request.urlopen(urllib.request.Request(url, data=body, headers=headers, method="PATCH"), timeout=10).close()
    except Exception as e:
        print(f"[feedback] gist update failed: {e}")


def ask(question):
    with st.spinner("Searching 557 W3C pages…"):
        start = time.perf_counter()
        result = pipeline.answer(question)
        result["seconds"] = round(time.perf_counter() - start, 1)
        result["cost"] = cost_usd(result.get("usage", {}))
    st.session_state.update(result=result, question=question, voted=None)


def chips(prefix):
    with st.container(key=prefix + "s" if prefix == "chip" else "idkchips"):
        cols = st.columns(2)
        for i, (sc, q) in enumerate(EXAMPLES):
            if cols[i % 2].button(f"{sc} · {q}", key=f"{prefix}{i}", use_container_width=True):
                ask(q)
                st.rerun()


def answer_html(text):
    """Escape the answer, keep **bold** and line breaks, colour SC numbers, turn [n] into citation pills."""
    t = html.escape(text)
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = SC_RE.sub(lambda m: sc_pill(m.group(0)), t)
    t = re.sub(r"\[(\d+)\]", r'<span class="cite">\1</span>', t)
    return t.replace("\n", "<br>")


def sc_of(chunk):
    m = SC_RE.search(f"{chunk['title']} {chunk['section']}")
    return m.group(0) if m else None


def searched_html(queries):
    if not queries:
        return ""
    return ('<div class="searched"><span>Searched for:</span>'
            + "".join(f'<span class="qchip">{html.escape(q)}</span>' for q in queries) + "</div>")


def show_answer(r):
    chunks = r.get("chunks", [])
    cited = [(i, c) for i, c in enumerate(chunks, start=1) if c["id"] in set(r.get("citations", []))]
    first_sc = sc_of(cited[0][1]) if cited else None
    border = STYLE[principle_of(first_sc)][0]
    n = len(cited)
    left, right = st.columns([8, 4], gap="medium")
    with left:
        st.markdown(h(f"""
        <div class="acard" style="border-left-color:{border}">
          <div class="ahead"><div class="l"><span class="dot"></span><h4>Answer</h4>
            <span class="grounded">Grounded in {n} source{'s' if n != 1 else ''}</span></div>
            <span class="lat">{icon("timer", 15, "#64748B")}Answered in {r['seconds']} s · ${r['cost']:.4f}</span></div>
          <div class="qline">You asked: <b>{html.escape(st.session_state.question)}</b></div>
          <div class="atext">{answer_html(r['answer'])}</div>
        </div>"""), unsafe_allow_html=True)
        votes()
        with st.expander(f"Show retrieved passages ({len(chunks)})"):
            st.markdown(searched_html(r.get("rewrite", {}).get("queries")), unsafe_allow_html=True)
            for i, c in enumerate(chunks, start=1):
                sc = sc_of(c)
                st.markdown(h(f"""<div class="passage"><div class="ph"><span class="cite">{i}</span> {html.escape(c['section'])}
                    {(' ' + sc_pill(sc)) if sc else ''}</div>{html.escape(c['text'][:700])}{'…' if len(c['text']) > 700 else ''}</div>"""),
                            unsafe_allow_html=True)
    with right:
        items = ""
        for i, c in cited:
            sc = sc_of(c)
            items += (f'<div class="src"><span class="n">{i}</span><div><div class="t">{html.escape(c["section"])}</div>'
                      f'<div class="s">{html.escape(c["title"])}{(" · " + sc_pill(sc)) if sc else ""}</div>'
                      f'<a href="{html.escape(c["url"])}" target="_blank">Open on w3.org ↗</a></div></div>')
        if not items:
            items = '<div class="s" style="font-size:13px;color:#64748B">No specific passage was cited.</div>'
        st.markdown(h(f"""<div class="scard"><div class="shead"><span>SOURCES</span>
            <span>{n} reference{'s' if n != 1 else ''}</span></div>{items}</div>"""), unsafe_allow_html=True)


def votes():
    r = st.session_state.result
    if st.session_state.voted is not None:
        st.markdown('<p class="thanks">Thanks for the feedback!</p>', unsafe_allow_html=True)
        return
    with st.container(key="votes"):
        label, up, down, _ = st.columns([2, 1, 1, 5])
        label.markdown("<div style='padding-top:8px;font-size:13px;color:#475569'>Was this helpful?</div>", unsafe_allow_html=True)
        vote = True if up.button("👍", key="up") else False if down.button("👎", key="down") else None
    if vote is not None:
        save_vote({"time": datetime.now(timezone.utc).isoformat(), "question": st.session_state.question,
                   "answer": r["answer"], "helpful": vote, "idk_reason": r.get("idk_reason"),
                   "citations": r.get("citations", []), "seconds": r["seconds"],
                   "cost_usd": r["cost"], "model": pipeline.MODEL})
        st.session_state.voted = vote
        st.rerun()


def show_idk(r):
    reason = IDK_TEXT.get(r.get("idk_reason"), "")
    st.markdown(h(f"""
    <div class="idk">
      <svg width="80" height="80" viewBox="0 0 80 80" fill="none" aria-hidden="true">
        <circle cx="40" cy="40" r="36" fill="#F0FDF9" stroke="#CCFBEF" stroke-width="1.5"/>
        <path d="M40 50C35.5 47 28 47 21 49V28C28 26 35.5 26 40 29C44.5 26 52 26 59 28V49C52 47 44.5 47 40 50Z" fill="#F8FAFC" stroke="#7C3AED" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>
        <path d="M40 29V50" stroke="#7C3AED" stroke-width="2.2" stroke-linecap="round"/>
        <circle cx="48" cy="37" r="13" fill="#EFF6FF" fill-opacity=".85" stroke="#3B82F6" stroke-width="2.6"/>
        <path d="M48 34L49 37L52 38L49 39L48 42L47 39L44 38L47 37L48 34Z" fill="#10B981"/>
        <path d="M57 46L66 55" stroke="#F59E0B" stroke-width="3.5" stroke-linecap="round"/>
      </svg>
      <h3>I couldn't find this in the WCAG 2.2 documents.</h3>
      <p>{reason} The Librarian only answers from the official W3C accessibility documentation.
         Try rephrasing, or ask about a specific success criterion.</p>
      <div style="display:flex;justify-content:center">{searched_html(r.get("rewrite", {}).get("queries"))}</div>
      <div class="or">OR TRY ONE OF THESE</div>
    </div>"""), unsafe_allow_html=True)
    chips("idkchip")


# ---------- page ----------
warm_up()

st.markdown(h("""<div class="hero"><div class="h1">Ask anything about <span>WCAG&nbsp;2.2</span></div>
<p>Answers straight from the official W3C documents, with sources for every claim.</p></div>"""), unsafe_allow_html=True)

with st.container(key="askbox"):
    with st.form("ask", clear_on_submit=False, border=False):
        q_col, b_col = st.columns([6, 1])
        question = q_col.text_input("Your question about WCAG 2.2", placeholder="e.g. How big should a touch target be?",
                                    label_visibility="collapsed")
        submitted = b_col.form_submit_button("Ask →", use_container_width=True)
if submitted and question.strip():
    ask(question.strip())

if "result" not in st.session_state:
    chips("chip")
    st.markdown(h("""<div class="cards">
    <div class="fcard"><span class="ic" style="background:#DBEAFE">""" + icon("shield", 22, "#1D4ED8") + """</span>
      <h3>Official sources only</h3><p>Answers come only from the W3C WCAG 2.2 Recommendation, Understanding and Techniques pages.</p>
      <div class="ft" style="color:#1D4ED8">557 W3C PAGES INDEXED</div></div>
    <div class="fcard"><span class="ic" style="background:#EDE9FE">""" + icon("quote", 22, "#7C3AED") + """</span>
      <h3>Every claim cited</h3><p>Numbered citations point to the exact W3C page and section, so you can check every answer yourself.</p>
      <div class="ft" style="color:#7C3AED">SOURCES NEXT TO EVERY ANSWER</div></div>
    <div class="fcard"><span class="ic" style="background:#CCFBF1">""" + icon("help", 22, "#0F766E") + """</span>
      <h3>Says when it doesn't know</h3><p>If the WCAG documents don't cover your question, it tells you instead of guessing.</p>
      <div class="ft" style="color:#0F766E">NO GUESSING</div></div>
    </div>"""), unsafe_allow_html=True)
else:
    st.write("")
    r = st.session_state.result
    if r["answer"] == pipeline.IDK:
        show_idk(r)
    else:
        show_answer(r)

st.markdown(h("""<div class="about" id="about"><h3>About The Librarian</h3>
<p>A question-answering assistant for the Web Content Accessibility Guidelines (WCAG) 2.2, built for the CS496 AI Engineering
course. It uses retrieval-augmented generation (RAG):</p>
<ol><li><b style="color:#1D4ED8">1</b>Searches 557 W3C pages by keywords and by meaning.</li>
<li><b style="color:#7C3AED">2</b>A reranker keeps the 5 most relevant passages.</li>
<li><b style="color:#0F766E">3</b>An LLM answers using only those passages and cites them.</li>
<li><b style="color:#B45309">4</b>If nothing relevant is found, it says it doesn't know.</li></ol>
<div class="warn">It can still make mistakes. Always check the cited W3C source before relying on an answer.</div></div>
<div class="foot">The Librarian · Built for CS496 AI Engineering · Sources: W3C WCAG 2.2</div>"""), unsafe_allow_html=True)

if FEEDBACK_FILE.exists():
    with st.expander("Team: download votes"):
        st.download_button("Download feedback.jsonl", FEEDBACK_FILE.read_bytes(), "feedback.jsonl")