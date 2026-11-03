# The Librarian: cited answers from WCAG 2.2

CS496 AI Engineering · Project 2 · Dr Abdeldjalil Labed · MedTech · November 2026

Team: Khadija Chtourou, Maya Boussora, Mayssa Ghabarou · Live app: https://librarian-wcag.streamlit.app/

## Overview

The Librarian is a retrieval-augmented question-answering service over the official W3C WCAG 2.2 documentation (557 pages), for developers who need to know what the accessibility rules require. It answers only from these documents, cites every sentence, and says "I don't know" when they do not contain the answer.

![System overview](system_diagram.png)

*Figure 1. System overview: building the index (A) and answering a question (B).*

## Chunking

We scraped the WCAG 2.2 Recommendation, *Understanding* and *Techniques* pages, keeping the title, section and URL of every passage. Pages are split by heading, then into chunks of up to 375 words (about 500 tokens) with a two-sentence overlap, never cutting a sentence. Removing duplicate URLs and a repeated "Key Terms" glossary took the corpus from 4,749 to **4,065 chunks**.

## Embedding

Each chunk is embedded with **all-MiniLM-L6-v2** (384 dimensions), which runs locally on CPU at no cost. A **BM25** keyword index keeps exact identifiers such as "1.4.3" or "4.5:1", which embeddings tend to blur.

## Vector database

The vectors are stored in a flat **numpy file** (4,065 × 384, exact cosine search) and BM25 is built in memory. At this size exact search takes milliseconds, so a vector database would add nothing. The file is committed to git, so the deployed app needs no build step.

## Retrieval

1. **Rewrite.** A small model (**gpt-5-nano**) rejects off-topic questions (no search, no answer call), translates the question to English and turns it into 1–3 WCAG search queries; an unusable reply is retried once. On 15 hard questions this raised the score from 8/15 to 14/15.
2. **Hybrid search.** BM25 and vector search each return their top 30, merged with reciprocal rank fusion (RRF).
3. **Reranking.** A cross-encoder (**ms-marco-MiniLM-L-6-v2**) reads the question and each of about 20 candidates together; each chunk is scored against the question and every query and keeps its best score, and the best 5 are kept. It is the largest gain in retrieval (R@1 0.56 → 0.72, MRR@10 0.69 → 0.80, Table 1), at about 1–3 s per question on a laptop CPU, depending on the machine. Off-topic chunks score around −11, so if even the best score is below 0, no answer is generated ("I don't know").

## Generation

**gpt-6-luna** (low reasoning effort) receives the 5 numbered chunks and must answer only from them, with a citation [n] on every sentence and the conformance level (A, AA or AAA) stated without mixing levels; it mentions exceptions and answers in the user's language. Uncited closing sentences are removed, an answer that says "I don't know" without citing anything counts as a refusal, and citations are mapped back to the source chunks. The app runs on Streamlit Community Cloud, and user votes (helpful / not helpful) are saved to a GitHub gist.

## Evaluation

The eval set has 122 questions (110 answerable, 12 out of scope), each with a gold passage; answers are judged by gpt-4.1-mini. The Week 8 run used the earlier 124-question version.

**Table 1.** Retrieval comparison (110 answerable questions; search time on a laptop CPU).

| Method | R@1 | R@5 | R@10 | MRR@10 | Search time |
|---|---|---|---|---|---|
| BM25 only | 0.59 | 0.85 | 0.92 | 0.70 | 36 ms |
| Vector only | 0.48 | 0.73 | 0.81 | 0.59 | 32 ms |
| Hybrid (RRF) | 0.56 | 0.86 | **0.96** | 0.69 | 70 ms |
| Hybrid + reranker | **0.72** | **0.93** | 0.95 | **0.80** | 2,779 ms |

**Table 2.** Week 8 optimisation (124 questions, same judge): low reasoning effort, and gpt-6-luna instead of gpt-5-mini.

| | Before | After | Change |
|---|---|---|---|
| Answer accuracy | 74.2% | 75.8% | +1.6 pts |
| "I don't know" accuracy | 86.3% | 95.2% | +8.9 pts |
| Faithfulness | 98.5% | 90.9% | −7.6 pts |
| Cost per request | $0.0032 | $0.00039 | −88% |
| p95 latency | 34.7 s | 12.6 s | −64% |

The target (−50% cost or p95, at most 2 accuracy points lost) is met.

**Cost model.** At $0.00039 per request, the models cost about $0.60 a month at 50 requests a day, and about $58 a month at 100 times that traffic. Embedding, search and reranking run locally, and hosting is free.

**Known failure cases.** The CAPTCHA rule (SC 3.3.8) is rarely retrieved, so that answer is incomplete; low reasoning effort gives shorter, sometimes partial answers; and faithfulness dropped, mostly because of uncited first sentences and refusals counted as answers, which we have since addressed in the prompt and the checks.

## What we learned

- **Retrieval decides answer quality.** Vector search alone found the right passage in the top 5 only 73% of the time; hybrid search with reranking reached 93%.
- **Users do not speak the corpus's language.** Rewriting questions into WCAG terms took our hard set from 8/15 to 14/15.
- **Measure where the cost comes from.** Most of it was hidden reasoning tokens, not context length: sending 3 chunks instead of 5 saved nothing.
- **Small tests are noisy.** One question is worth 7 points on a 15-question set, so final decisions need the full eval.
- **"I don't know" is a feature.** Checks before the answer model avoid wrong answers and save money.
