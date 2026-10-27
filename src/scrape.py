"""Download WCAG 2.2 pages to data/raw/. Polite: caches files, sleeps between requests.
Crawls each index page up to 2 levels deep, staying under the given URL prefix.
Run: python -m src.scrape [--limit N]   (N = max pages per index, for quick tests)"""
import json, re, sys, time, pathlib, requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urldefrag, urlparse

RAW = pathlib.Path("data/raw"); RAW.mkdir(parents=True, exist_ok=True)
HEADERS = {"User-Agent": "CS496-student-project (educational RAG)"}
SPEC = "https://www.w3.org/TR/WCAG22/"
SEEDS = [
    "https://www.w3.org/WAI/WCAG22/Understanding/",
    "https://www.w3.org/WAI/WCAG22/Techniques/",
]
SKIP_EXT = (".css", ".js", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".pdf", ".zip", ".xml", ".json", ".ico", ".woff", ".woff2")
MAX_DEPTH = 2

def slug(url):
    return re.sub(r"[^a-z0-9]+", "-", url.replace("https://www.w3.org/", "").lower()).strip("-")[:120]

def fetch(url):
    f = RAW / (slug(url) + ".html")
    if f.exists():
        return f.read_text(encoding="utf-8")
    try:
        r = requests.get(url, headers=HEADERS, timeout=30); r.raise_for_status()
    except Exception as e:
        print("FAIL", url, e); return None
    f.write_text(r.text, encoding="utf-8"); time.sleep(0.3)
    return r.text

def links_under(html, base, prefix):
    out = set()
    for a in BeautifulSoup(html, "lxml").find_all("a", href=True):
        u = urldefrag(urljoin(base, a["href"]))[0].split("?")[0]
        if u.startswith(prefix) and not urlparse(u).path.lower().endswith(SKIP_EXT):
            out.add(u)
    return out

def crawl(seed, limit=None):
    seen, frontier, pages = {seed}, [seed], []
    for depth in range(MAX_DEPTH + 1):
        nxt = []
        for u in frontier:
            html = fetch(u)
            if html is None: continue
            if u != seed: pages.append(u)
            if limit and len(pages) >= limit: return pages
            if depth < MAX_DEPTH:
                for l in sorted(links_under(html, u, seed)):
                    if l not in seen: seen.add(l); nxt.append(l)
            if len(pages) and len(pages) % 25 == 0: print(f"  {seed.split('/')[-2]}: {len(pages)} pages")
        frontier = nxt
    return pages

def main():
    limit = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else None
    urls = [SPEC]; fetch(SPEC)
    for seed in SEEDS:
        found = crawl(seed, limit); print(seed, "->", len(found), "pages")
        urls += found
    mapping = {slug(u) + ".html": u for u in urls}
    (RAW / "_urls.json").write_text(json.dumps(mapping, indent=1))
    print("done:", len(mapping), "pages total")

if __name__ == "__main__":
    main()
