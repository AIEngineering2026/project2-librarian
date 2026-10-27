"""Download WCAG 2.2 pages to data/raw/. Polite: caches files, sleeps between requests.
Run: python -m src.scrape [--limit N]"""
import json, re, sys, time, pathlib, requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urldefrag

RAW = pathlib.Path("data/raw"); RAW.mkdir(parents=True, exist_ok=True)
HEADERS = {"User-Agent": "CS496-student-project (educational RAG)"}
SPEC = "https://www.w3.org/TR/WCAG22/"
INDEXES = {
    "https://www.w3.org/WAI/WCAG22/Understanding/": "/WAI/WCAG22/Understanding/",
    "https://www.w3.org/WAI/WCAG22/Techniques/": "/WAI/WCAG22/Techniques/",
}

def slug(url):
    return re.sub(r"[^a-z0-9]+", "-", url.replace("https://www.w3.org/", "").lower()).strip("-")[:120]

def get(url):
    r = requests.get(url, headers=HEADERS, timeout=30); r.raise_for_status(); return r.text

def links_from(index_url, prefix):
    soup = BeautifulSoup(get(index_url), "lxml")
    out = set()
    for a in soup.find_all("a", href=True):
        u = urldefrag(urljoin(index_url, a["href"]))[0]
        if u.startswith("https://www.w3.org" + prefix) and u.endswith(".html"):
            out.add(u)
    return sorted(out)

def main():
    limit = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else None
    urls = [SPEC]
    for idx, prefix in INDEXES.items():
        found = links_from(idx, prefix); print(idx, "->", len(found), "links")
        urls += found[:limit] if limit else found
    mapping = {}
    for i, u in enumerate(urls, 1):
        f = RAW / (slug(u) + ".html"); mapping[f.name] = u
        if not f.exists():
            try: f.write_text(get(u), encoding="utf-8"); time.sleep(0.3)
            except Exception as e: print("FAIL", u, e); continue
        if i % 25 == 0: print(i, "/", len(urls))
    (RAW / "_urls.json").write_text(json.dumps(mapping, indent=1))
    print("done:", len(mapping), "pages")

if __name__ == "__main__":
    main()
