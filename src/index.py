"""Build BM25 + Chroma indexes from data/chunks.jsonl. Run: python -m src.index"""
import json, pickle, pathlib, re
from rank_bm25 import BM25Okapi
import chromadb
from sentence_transformers import SentenceTransformer

IDX = pathlib.Path("data/index"); IDX.mkdir(parents=True, exist_ok=True)
EMB = "sentence-transformers/all-MiniLM-L6-v2"

def tok(s): return re.findall(r"\w+", s.lower())

def main():
    chunks = [json.loads(l) for l in open("data/chunks.jsonl", encoding="utf-8")]
    pickle.dump((chunks, BM25Okapi([tok(c["text"]) for c in chunks])), open(IDX / "bm25.pkl", "wb"))
    model = SentenceTransformer(EMB)
    embs = model.encode([c["text"] for c in chunks], batch_size=64, show_progress_bar=True, normalize_embeddings=True)
    client = chromadb.PersistentClient(path=str(IDX / "chroma"))
    try: client.delete_collection("wcag")
    except Exception: pass
    col = client.create_collection("wcag", metadata={"hnsw:space": "cosine"})
    for i in range(0, len(chunks), 500):
        b = chunks[i:i + 500]
        col.add(ids=[c["id"] for c in b], embeddings=embs[i:i + 500].tolist(),
                documents=[c["text"] for c in b],
                metadatas=[{"title": c["title"], "section": c["section"], "url": c["url"]} for c in b])
    print("indexed", len(chunks), "chunks")

if __name__ == "__main__":
    main()
