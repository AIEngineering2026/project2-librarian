"""Turn data/raw/*.html into data/chunks.jsonl, split by heading.
Size is in WORDS (~0.75 words per token, so 375 words ~ 500 tokens). Test several sizes!
Run: python -m src.chunk [--words 375] [--overlap 50]"""
import json, sys, pathlib
from bs4 import BeautifulSoup

RAW = pathlib.Path("data/raw"); OUT = pathlib.Path("data/chunks.jsonl")
HEAD = {"h2", "h3", "h4"}; BLOCK = ["h2", "h3", "h4", "p", "li", "pre", "td", "dd", "dt"]

def arg(name, default):
    return int(sys.argv[sys.argv.index(name) + 1]) if name in sys.argv else default

def sections(soup):
    root = soup.find("main") or soup.body or soup
    for t in root(["script", "style", "nav", "header", "footer"]): t.decompose()
    h1 = root.find("h1") or soup.find("h1")
    title = h1.get_text(" ", strip=True) if h1 else (soup.title.string if soup.title else "")
    cur, buf = "Intro", []
    for el in root.find_all(BLOCK):
        txt = el.get_text(" ", strip=True)
        if not txt: continue
        if el.name in HEAD:
            if buf: yield title, cur, " ".join(buf)
            cur, buf = txt, []
        else:
            buf.append(txt)
    if buf: yield title, cur, " ".join(buf)

def windows(text, size, overlap):
    w = text.split(); step = max(1, size - overlap)
    for i in range(0, max(1, len(w)), step):
        yield " ".join(w[i:i + size])
        if i + size >= len(w): break

def main():
    size, overlap = arg("--words", 375), arg("--overlap", 50)
    urls = json.loads((RAW / "_urls.json").read_text())
    n = 0
    with OUT.open("w", encoding="utf-8") as out:
        for fname, url in urls.items():
            f = RAW / fname
            if not f.exists(): continue
            soup = BeautifulSoup(f.read_text(encoding="utf-8"), "lxml")
            for title, sec, text in sections(soup):
                if len(text.split()) < 15: continue
                for j, piece in enumerate(windows(text, size, overlap)):
                    n += 1
                    out.write(json.dumps({"id": f"{f.stem}-{n:05d}", "text": f"{title} - {sec}\n{piece}",
                                          "title": title, "section": sec, "url": url}, ensure_ascii=False) + "\n")
    print("chunks:", n, "->", OUT)

if __name__ == "__main__":
    main()
