"""Review tool for the eval questions (all from the terminal).
  python eval/review_tool.py split                      split drafts into data/review/{maya,mayssa,khadija}.jsonl
  python eval/review_tool.py show NAME [FROM TO]        print the numbered questions of one review file
  python eval/review_tool.py drop NAME N [N ...]        delete questions by number (numbers are from `show`)
  python eval/review_tool.py edit NAME N question|answer "new text"
  python eval/review_tool.py merge                      check everything and write data/eval.jsonl
Everyone edits ONLY their own file. Extra files (e.g. data/review/maya_extra.jsonl) are merged too."""
import json, random, re, sys, pathlib

NAMES = ["maya", "mayssa", "khadija"]
D = pathlib.Path("data"); R = D / "review"
NEED = ["question", "answer", "source_url", "source_passage", "answerable"]

def read(path): return [json.loads(l) for l in open(path, encoding="utf-8-sig") if l.strip()]
def norm_url(u): return re.sub(r"\.html$", "", u.strip()).rstrip("/")
def write(path, rows):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        for r in rows: f.write(json.dumps(r, ensure_ascii=False) + "\n")

def split():
    rows, seen = [], set()
    for p in (D / "eval_draft.jsonl", D / "eval_draft2.jsonl"):
        if not p.exists(): continue
        for r in read(p):
            if r["question"] in seen: continue      # the 12 "I don't know" questions appear in both drafts
            seen.add(r["question"]); rows.append(r)
    random.Random(1).shuffle(rows)
    R.mkdir(parents=True, exist_ok=True)
    k = -(-len(rows) // len(NAMES))
    for i, name in enumerate(NAMES):
        part = rows[i * k:(i + 1) * k]; write(R / f"{name}.jsonl", part)
        print(f"{name:8} {len(part)} questions -> data/review/{name}.jsonl")
    print("total:", len(rows))

def show(name, a="1", b="999999"):
    rows = read(R / f"{name}.jsonl")
    for i, r in enumerate(rows, 1):
        if int(a) <= i <= int(b):
            print(f"{i:3}. [{'A' if r['answerable'] else 'IDK'}] {r['question']}\n       ans: {r['answer'][:170]}")
            if r["answerable"]: print(f"       src: {r['source_url'].split('/')[-1]} | {r['source_passage'][:150]}")
    print(f"\n{len(rows)} questions in data/review/{name}.jsonl")

def drop(name, *nums):
    p = R / f"{name}.jsonl"; rows = read(p); kill = {int(x) for x in nums}
    write(p, [r for i, r in enumerate(rows, 1) if i not in kill])
    print(f"deleted {len(kill)}; {len(rows) - len(kill)} left. Numbers have changed: run `show` again.")

def edit(name, num, field, text):
    if field not in ("question", "answer"): sys.exit("field must be question or answer")
    p = R / f"{name}.jsonl"; rows = read(p); rows[int(num) - 1][field] = text; write(p, rows)
    print("updated", field, "of", num)

def merge():
    out, seen, bad = [], set(), 0
    for p in sorted(R.glob("*.jsonl")):
        for n, line in enumerate(open(p, encoding="utf-8-sig"), 1):
            if not line.strip(): continue
            try: r = json.loads(line)
            except Exception: print(f"BAD JSON  {p.name}:{n}"); bad += 1; continue
            miss = [k for k in NEED if k not in r]
            if miss: print(f"MISSING {miss}  {p.name}:{n}"); bad += 1; continue
            if r["answerable"]:
                if not (r["question"].strip() and r["answer"].strip() and r["source_url"].startswith("http") and r["source_passage"].strip()):
                    print(f"INCOMPLETE  {p.name}:{n}  {r['question'][:50]}"); bad += 1; continue
                r["source_url"] = norm_url(r["source_url"])
            else:
                r.update(answer="I don't know", source_url="", source_passage="")
            if r["question"].strip().lower() in seen: print(f"DUPLICATE  {p.name}:{n}"); continue
            seen.add(r["question"].strip().lower()); out.append({k: r[k] for k in NEED})
    write(D / "eval.jsonl", out)
    a = sum(r["answerable"] for r in out)
    print(f"\ndata/eval.jsonl: {len(out)} questions ({a} answerable, {len(out) - a} unanswerable), {bad} problem lines skipped")
    if a < 100: print(f"Need 100+ answerable questions: {100 - a} more to go.")

if __name__ == "__main__":
    sys.stdout.reconfigure(errors="replace")
    cmds = {"split": split, "show": show, "drop": drop, "edit": edit, "merge": merge}
    if len(sys.argv) < 2 or sys.argv[1] not in cmds: print(__doc__)
    else: cmds[sys.argv[1]](*sys.argv[2:])
