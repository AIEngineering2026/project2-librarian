"""Turn data/raw/*.html into data/chunks.jsonl.
1) split by heading  2) pack whole sentences/blocks up to --words  3) overlap by --overlap sentences
4) drop chunks whose body text already exists (e.g. 'Key Terms' repeated on many pages).
Size is in WORDS (~0.75 words per token, so 375 words ~ 500 tokens). Test several sizes!
Run: python -m src.chunk [--words 375] [--overlap 2]"""
import json, re, sys, pathlib
from bs4 import BeautifulSoup

RAW = pathlib.Path("data/raw"); OUT = pathlib.Path("data/chunks.jsonl")
HEAD = {"h2", "h3", "h4"}; BLOCK = ["h2", "h3", "h4", "p", "li", "pre", "td", "dd", "dt"]
SENT_SPLIT = re.compile(r'(?<=[.!?])\s+(?=[A-Z0-9"\u201c(\[])')

def arg(name, default):
    return int(sys.argv[sys.argv.index(name) + 1]) if name in sys.argv else default

def sections(soup):
    """yield (title, section_heading, [block texts])"""
    root = soup.find("main") or soup.body or soup
    for t in root(["script", "style", "nav", "header", "footer"]): t.decompose()
    h1 = root.find("h1") or soup.find("h1")
    title = h1.get_text(" ", strip=True) if h1 else (soup.title.string if soup.title else "")
    cur, buf = "Intro", []
    for el in root.find_all(BLOCK):
        txt = el.get_text(" ", strip=True)
        if not txt: continue
        if el.name in HEAD:
            if buf: yield title, cur, buf
            cur, buf = txt, []
        else:
            buf.append(txt)
    if buf: yield title, cur, buf

def units(blocks, size):
    """blocks -> list of sentence-like units; a unit longer than `size` words is hard-split."""
    out = []
    for b in blocks:
        for s in SENT_SPLIT.split(b):
            w = s.split()
            if not w: continue
            if len(w) <= size: out.append(s.strip())
            else: out += [" ".join(w[i:i + size]) for i in range(0, len(w), size)]
    return out

def pack(us, size, overlap):
    """pack units into chunks of <= size words; start each new chunk with the last `overlap` units."""
    chunk, words, fresh = [], 0, False
    for u in us:
        n = len(u.split())
        if chunk and words + n > size and fresh:
            yield " ".join(chunk)
            chunk = chunk[-overlap:] if overlap else []
            while chunk and sum(len(x.split()) for x in chunk) > size // 4:   # overlap stays small
                chunk.pop(0)
            words, fresh = sum(len(x.split()) for x in chunk), False
        chunk.append(u); words += n; fresh = True
    if chunk and fresh: yield " ".join(chunk)

def norm(s): return re.sub(r"\W+", " ", s.lower()).strip()

def main():
    size, overlap = arg("--words", 375), arg("--overlap", 2)
    urls = json.loads((RAW / "_urls.json").read_text())
    n = dups = 0
    seen_urls, seen_bodies = set(), set()
    with OUT.open("w", encoding="utf-8") as out:
        for fname, url in urls.items():
            f = RAW / fname
            if not f.exists(): continue
            url = re.sub(r"\.html$", "", url).rstrip("/")   # same page can appear with and without .html
            if url in seen_urls: continue
            seen_urls.add(url)
            soup = BeautifulSoup(f.read_text(encoding="utf-8"), "lxml")
            for title, sec, blocks in sections(soup):
                if len(" ".join(blocks).split()) < 15: continue
                for piece in pack(units(blocks, size), size, overlap):
                    key = norm(piece)
                    if key in seen_bodies: dups += 1; continue
                    seen_bodies.add(key); n += 1
                    out.write(json.dumps({"id": f"{f.stem}-{n:05d}", "text": f"{title} - {sec}\n{piece}",
                                          "title": title, "section": sec, "url": url}, ensure_ascii=False) + "\n")
    print(f"chunks: {n} -> {OUT}  (removed {dups} repeated chunks)")

if __name__ == "__main__":
    main()
