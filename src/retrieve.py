"""The shared contract: retrieve(query, k, mode) -> list[dict] (chunk + score).
mode: "bm25" | "vector" | "hybrid" (reciprocal rank fusion)."""
import pickle, pathlib, re
import chromadb
from sentence_transformers import SentenceTransformer

IDX = pathlib.Path("data/index"); EMB = "sentence-transformers/all-MiniLM-L6-v2"
_state = {}

def _load():
    if not _state:
        chunks, bm25 = pickle.load(open(IDX / "bm25.pkl", "rb"))
        _state.update(chunks=chunks, bm25=bm25, by_id={c["id"]: c for c in chunks},
                      model=SentenceTransformer(EMB),
                      col=chromadb.PersistentClient(path=str(IDX / "chroma")).get_collection("wcag"))
    return _state

def _bm25(q, n):
    s = _load(); scores = s["bm25"].get_scores(re.findall(r"\w+", q.lower()))
    top = sorted(range(len(scores)), key=lambda i: -scores[i])[:n]
    return [(s["chunks"][i]["id"], float(scores[i])) for i in top]

def _vector(q, n):
    s = _load(); e = s["model"].encode([q], normalize_embeddings=True).tolist()
    r = s["col"].query(query_embeddings=e, n_results=n)
    return [(i, 1 - d) for i, d in zip(r["ids"][0], r["distances"][0])]

def retrieve(query, k=5, mode="hybrid", pool=30):
    s = _load()
    if mode == "bm25": ranked = _bm25(query, k)
    elif mode == "vector": ranked = _vector(query, k)
    else:
        fused = {}
        for lst in (_bm25(query, pool), _vector(query, pool)):
            for rank, (cid, _) in enumerate(lst):
                fused[cid] = fused.get(cid, 0) + 1 / (60 + rank)
        ranked = sorted(fused.items(), key=lambda x: -x[1])[:k]
    return [{**s["by_id"][cid], "score": sc} for cid, sc in ranked]
