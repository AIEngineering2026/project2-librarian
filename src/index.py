"""Build the vector index: one normalised embedding per chunk, saved as a flat numpy file (no vector database needed).
Run: python -m src.index      (about 3 minutes on a laptop; then commit data/index/embeddings.npy and meta.json)
Optional env vars: CHUNKS_PATH (default data/chunks.jsonl), INDEX_DIR (default data/index)."""
import hashlib, json, os, pathlib
import numpy as np

EMB = "sentence-transformers/all-MiniLM-L6-v2"

def ids_hash(chunks):
    return hashlib.sha1("\n".join(c["id"] for c in chunks).encode()).hexdigest()

def embed(texts, show_progress=True):
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(EMB)
    return model.encode(texts, batch_size=64, show_progress_bar=show_progress, normalize_embeddings=True).astype("float32")

def build(chunks, index_dir):
    index_dir = pathlib.Path(index_dir); index_dir.mkdir(parents=True, exist_ok=True)
    embs = embed([c["text"] for c in chunks])
    np.save(index_dir / "embeddings.npy", embs)
    (index_dir / "meta.json").write_text(json.dumps({"model": EMB, "n": len(chunks), "ids_sha1": ids_hash(chunks)}))
    return embs

def main():
    chunks_path = os.getenv("CHUNKS_PATH", "data/chunks.jsonl"); index_dir = os.getenv("INDEX_DIR", "data/index")
    chunks = [json.loads(l) for l in open(chunks_path, encoding="utf-8") if l.strip()]
    embs = build(chunks, index_dir)
    print(f"indexed {len(chunks)} chunks -> {index_dir}/embeddings.npy ({embs.nbytes / 1e6:.1f} MB)")

if __name__ == "__main__":
    main()
