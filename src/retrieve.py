"""The shared contract: retrieve(query, k=5, mode="hybrid") -> list[dict] (chunk fields + "score").
mode: "bm25" | "vector" | "hybrid" (reciprocal rank fusion of the two).
BM25 is built in memory from data/chunks.jsonl at start-up (under a second). Vector search is an exact cosine
similarity on data/index/embeddings.npy, so there is no vector database and nothing to install or build on the cloud."""
import json, os, pathlib, re
import numpy as np
from rank_bm25 import BM25Okapi
from src.index import EMB, ids_hash, build

def tok(s): return re.findall(r"\w+", s.lower())

class Retriever:
    def __init__(self, chunks_path="data/chunks.jsonl", index_dir="data/index", embeddings=None):
        self.chunks = [json.loads(l) for l in open(chunks_path, encoding="utf-8") if l.strip()]
        self.bm25 = BM25Okapi([tok(c["text"]) for c in self.chunks])
        if embeddings is None:
            index_dir = pathlib.Path(index_dir)
            npy, meta = index_dir / "embeddings.npy", index_dir / "meta.json"
            if not (npy.exists() and meta.exists()):
                print("embeddings.npy not found: building it now (about 3 minutes)...")
                build(self.chunks, index_dir)
            m = json.loads(meta.read_text())
            if m["ids_sha1"] != ids_hash(self.chunks) or m["model"] != EMB:
                raise RuntimeError(f"{index_dir} does not match {chunks_path}. Run: python -m src.index")
            embeddings = np.load(npy)
        self.embs, self._model = embeddings, None

    def _bm25(self, q, n):
        scores = self.bm25.get_scores(tok(q))
        return [(int(i), float(scores[i])) for i in np.argsort(-scores, kind="stable")[:n]]

    def _vector(self, q, n):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(EMB)
        qv = self._model.encode([q], normalize_embeddings=True)[0]
        sims = self.embs @ qv
        return [(int(i), float(sims[i])) for i in np.argsort(-sims, kind="stable")[:n]]

    def search(self, query, k=5, mode="hybrid", pool=30):
        if mode == "bm25": ranked = self._bm25(query, k)
        elif mode == "vector": ranked = self._vector(query, k)
        else:
            fused = {}
            for lst in (self._bm25(query, pool), self._vector(query, pool)):
                for rank, (i, _) in enumerate(lst):
                    fused[i] = fused.get(i, 0) + 1 / (60 + rank)
            ranked = sorted(fused.items(), key=lambda x: -x[1])[:k]
        return [{**self.chunks[i], "score": sc} for i, sc in ranked]

_default = None

def retrieve(query, k=5, mode="hybrid", pool=30):
    global _default
    if _default is None:
        _default = Retriever(os.getenv("CHUNKS_PATH", "data/chunks.jsonl"), os.getenv("INDEX_DIR", "data/index"))
    return _default.search(query, k, mode, pool)
