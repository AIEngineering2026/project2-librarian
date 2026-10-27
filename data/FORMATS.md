# Shared formats (do not change without telling the others)

## data/chunks.jsonl  (one JSON per line)
{"id": "understanding-contrast-minimum-003", "text": "...", "title": "Contrast (Minimum)", "section": "Intent", "url": "https://..."}

## data/eval.jsonl  (one JSON per line)
{"question": "...", "answer": "...", "source_url": "https://...", "source_passage": "...", "answerable": true}
Keep ~10% with "answerable": false (answer = "I don't know").

## retrieve(query: str, k: int = 5, mode: str = "hybrid") -> list[dict]
Each dict = a chunk plus "score". mode in {"bm25", "vector", "hybrid"}.
