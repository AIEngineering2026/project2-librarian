# Librarian: plan for the final week

**Final demo: week of 2 Nov · remaining tasks due 6 Nov** · *Updated 28 Oct*

---

## 1. What changed

| | Before | Now |
|---|---|---|
| **LLMs** | Groq (free, 200k tokens/day limit) | **OpenAI** (course key): **gpt-6-luna** answers, **gpt-5-nano** rewrites, both with "low" effort |
| **Deployment** | Not possible (Hugging Face became paid) | **Streamlit Community Cloud** (free, enough memory for our models) |
| **Task tracking** | — | **Bloomi**: tasks added for each of us, with short bullets |

- Set the key in `.env`: `OPENAI_API_KEY=...` (never commit it). **Pull `main`**: the OpenAI version is merged.
- **Off-topic questions** (e.g. pizza) now stop right after the rewrite: "I don't know.", no search and no answer call.
- **Bloomi:** finished tasks are due **30 Oct**, remaining ones **6 Nov**. 👉 **Move your finished tasks to "To review"** (only Dr Labed can mark them Done) and check your bullets.

---

## 2. ✅ Week 8 results (OpenAI)

Khadija re-ran all the experiments on OpenAI (details in `docs/optimisation.md`):

| | p95 | Cost / question | Hard set (15 q) |
|---|---|---|---|
| Baseline (gpt-5-mini, default effort) | 35.0 s | $0.00308 | 13/15 |
| **Final = E8** (gpt-6-luna + low effort) | **9.8 s (−72%)** | **$0.000365 (−88%)** | **14/15** |

Faster and cheaper settings exist, but they lose quality. **These are the final settings**; they are now
the defaults in `src/pipeline.py`. The official accuracy comes from Maya's full eval (below).

---

## 3. Individual tasks left

### 👩‍💻 Khadija
1. ~~Re-run the Week 8 experiments on OpenAI~~ ✅ done → final settings sent to Maya
2. **Faithfulness fix** (a citation on every sentence), before Maya's optimised eval
3. **Deploy on Streamlit Cloud**, with a way to **keep the 👍/👎 votes** (the cloud deletes local files) → send the **URL** to everyone

### 📏 Maya
1. **Switch the judge to OpenAI: use `gpt-4.1-mini`**. It must differ from **both** compared models (gpt-5-mini and gpt-6-luna), so neither one grades itself. Use the same judge for both runs.
2. **Full eval, baseline**: can start **now**. Baseline = gpt-5-mini with default effort:
   ```
   $env:ANSWER_MODEL="gpt-5-mini"
   ...your eval command... --set REWRITE_EFFORT=None --set ANSWER_EFFORT=None
   Remove-Item Env:ANSWER_MODEL
   ```
3. **Threshold sweep** on the baseline answers → send the **recommended threshold** to Khadija
4. **Full eval, optimised (E8)**: pull `main` and run with **no extra settings** (E8 is the default). Best after Khadija's faithfulness fix
5. **Feedback summary**: once the site is live

### 🗂️ Mayssa
1. **Make the index work on Streamlit Cloud**: ⚠️ **urgent**, Khadija can't deploy without it
2. **Chunk-size results** (300 / 500 / 800 → recall)

---

## 4. Shared documents: all of us

Everyone updates the parts about their own work. "Started by" only says who wrote the first version.

| Document | Started by | Still to do (all of us) |
|---|---|---|
| **Report** (**2 pages**, sections given by Dr Labed) | Khadija (first, longer draft in `docs/report.md`) | ⏳ Get the sections from the photo (Maya). Then fit the content into those sections in **2 pages**, with the final numbers (OpenAI results, full eval, feedback, chunk sizes) |
| **System diagram** (new, asked by Dr Labed) | — | ⏳ Get the example photo (Maya). One diagram of how the whole system works: data → chunking → embeddings + BM25 index → question → rewrite → search → rerank → answer → web app → deployment, plus the eval loop |
| **README.md** | Khadija (full version) | OpenAI setup, deploy link, final results, check your Contributions |
| **Postmortem** (`docs/postmortem.md`) | Khadija | Add the new problems of this week; check the data and eval sections |
| **Optimisation report** (`docs/optimisation.md`) | Khadija | ✅ OpenAI results written · ⏳ Maya's full eval numbers (its section 4) |
| **design.md** (in the original brief) | — | Short technical doc on our choices: chunking + index choice (incl. chunk-size results), pipeline design, known failure cases |

---

## 5. Who needs whom

| Needs… | From… | For… |
|---|---|---|
| Khadija | **Mayssa**: index working on the cloud | Deploying the app |
| Khadija | **Maya**: recommended threshold | Final threshold in the app |
| Maya | **Khadija**: ✅ final settings · ⏳ faithfulness fix | Optimised eval + re-judge |
| Maya | **Khadija**: public URL | Collecting feedback |
| Shared docs | **Everyone**: final numbers | Report, README, optimisation report |
| Report + diagram | **Maya**: photos of Dr Labed's sections and diagram example | Following his format |

**Chains:**
- Mayssa's cloud index → Khadija deploys → classmates vote → feedback summary
- Maya's baseline → threshold → Khadija's final threshold · Khadija's faithfulness fix → Maya's optimised eval
- Everyone's final numbers → shared docs

---

## 6. Order

1. **Now, in parallel:** Khadija does the faithfulness fix · Mayssa does the cloud index · Maya switches the judge and runs the baseline
2. **Next:** optimised eval + threshold · deploy as soon as the index works
3. **End of the week:** a few days of feedback → summary → **all of us** finish the shared docs
4. **Final step (all of us):** the **system diagram** and the **2-page report** in Dr Labed's format, once all the numbers are final

📸 **Maya: please send the photos of the report sections and the diagram example**, so we can plan both.

---

## 7. ⚠️ Two rules

1. **Don't change `chunks.jsonl` anymore.** Any change means re-running the retrieval eval, the ablation, the Week 8 experiments and the full eval.
2. **Feedback must survive on the cloud.** The deploy must save votes somewhere we can read later (download button or permanent storage), or there's nothing to summarise.

---

## 8. Suggestion (only if you agree)

Maya has the most individual tasks left this week. To balance it, **Mayssa could take the feedback collection + summary**: it's independent and starts once the site is live. If you agree, we update Bloomi.