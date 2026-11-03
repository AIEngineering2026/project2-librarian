# The Librarian: cited answers from WCAG 2.2

CS496 AI Engineering · Project 2 · Dr Abdeldjalil Labed · MedTech · November 2026

Team: Khadija Chtourou, Maya Boussora, Mayssa Ghabarou · Live app: https://librarian-wcag.streamlit.app/
## Overview

The Librarian is a retrieval-augmented (RAG) question-answering service over the official W3C WCAG 2.2 documentation (557 pages), built for developers and designers who need to know what the accessibility rules require. It answers only from these documents, cites a source for every sentence, and says "I don't know" when the documents do not contain the answer.

![System overview](system_diagram.png)

*Figure 1. System overview: building the index (A) and answering a question (B).*

## Chunking

We scraped the WCAG 2.2 Recommendation, *Understanding* and *Techniques* pages with requests and BeautifulSoup, keeping the title, section and URL of every passage. Pages are split by heading, then into chunks of about 500 tokens with a small overlap, without cutting sentences. Two data problems had to be fixed: the same page reachable under two URLs, and a repeated "Key Terms" glossary that flooded keyword search. Removing both took the corpus from 4,749 to **4,065 chunks**.

## Embedding

Each chunk is embedded with **all-MiniLM-L6-v2** (sentence-transformers, 384 dimensions), which runs locally on CPU at no cost and is small enough for free hosting. Next to it, a **BM25** keyword index (rank_bm25) keeps exact identifiers such as "1.4.3" or "4.5:1", which embeddings tend to blur.

## Vector database

The vectors are stored in **Chroma** (persistent, cosine similarity) and the BM25 index in a file next to it. Chroma needs no server and is sufficient for 4,000 chunks. The index is not stored in git: the deployed app builds it automatically on its first start.

## Retrieval

1. **Rewrite.** Users rarely use WCAG vocabulary ("buttons too small?" instead of *target size*). A small model, **gpt-5-nano**, rejects off-topic questions, translates the question to English and writes 1–3 search queries. On our 15 hard test questions (vague wording, typos, French, SC numbers), this raised the score from 8/15 to 14/15.
2. **Hybrid search.** For the question and each query, BM25 and vector search each return their top 30, merged with reciprocal rank fusion (RRF).
3. **Reranking.** Hybrid search only compares shared words or separately computed vectors. The cross-encoder **ms-marco-MiniLM-L-6-v2** reads the query and each of about 20 candidates *together*, gives one relevance score, and keeps the best 5. It is the largest single gain in retrieval (R@1 0.56 → 0.72, MRR@10 0.69 → 0.80, Table 1). Its score also gives the first "I don't know": off-topic chunks score around −11, so if even the best score is below 0, no answer is generated.

## Generation

**gpt-6-luna** (low reasoning effort) receives the 5 numbered chunks. It must answer only from them, put a citation [n] on every sentence, state the conformance level (A, AA or AAA) without mixing levels, mention exceptions, and answer in the user's language. Uncited closing sentences are removed and citations are mapped back to the source chunks. The app runs on Streamlit Community Cloud, and user votes are stored in a GitHub gist.

## Evaluation

The eval set has 124 questions (112 answerable, 12 out of scope), each with a gold passage. Retrieval and generation are measured separately; answers are judged by gpt-4.1-mini.

**Table 1.** Retrieval ablation (112 answerable questions).

| Method | R@1 | R@5 | R@10 | MRR@10 | Search time |
|---|---|---|---|---|---|
| BM25 only | 0.59 | 0.85 | 0.92 | 0.69 | 12 ms |
| Vector only | 0.47 | 0.72 | 0.80 | 0.58 | 9 ms |
| Hybrid (RRF) | 0.56 | 0.87 | 0.96 | 0.69 | 24 ms |
| Hybrid + reranker | **0.72** | **0.93** | **0.96** | **0.80** | 803 ms |

**Table 2.** Week 8 optimisation (124 questions, same judge). Changes: low reasoning effort for both models, and gpt-6-luna instead of gpt-5-mini for answers.

| | Before | After | Change |
|---|---|---|---|
| Answer accuracy | 74.2% | 75.8% | +1.6 pts |
| "I don't know" accuracy | 86.3% | 95.2% | +8.9 pts |
| Faithfulness | 98.5% | 90.9% | −7.6 pts |
| Cost per request | $0.0032 | $0.00039 | −88% |
| p95 latency | 34.7 s | 12.6 s | −64% |

The target (−50% cost or p95, at most 2 accuracy points lost) is met. At 50 requests a day the models cost about $0.60 a month, and about $58 a month at 100 times that traffic; embedding, search and reranking run locally. The main remaining failures are a passage the search rarely finds (the CAPTCHA rule, SC 3.3.8), shorter answers at low effort, and lower faithfulness, mostly uncited first sentences, which we have since addressed in the prompt.

## What we learned

- **Retrieval decides answer quality.** Vector search alone found the right passage in the top 5 only 72% of the time; hybrid search with reranking reached 93%. Technical text needs exact keywords.
- **Users do not speak the corpus's language.** Rewriting questions into WCAG terms took our hard test set from 8/15 to 14/15.
- **Measure where the cost comes from.** Most of the cost was hidden reasoning tokens, not context length: sending 3 chunks instead of 5 saved nothing.
- **Small tests are noisy.** One question is worth 7 points on a 15-question set, so final decisions need the full 124-question eval.
- **"I don't know" is a feature.** Checks before the answer model avoid wrong answers and also save money.
