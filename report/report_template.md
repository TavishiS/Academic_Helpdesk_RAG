# Academic Helpdesk Agent: Report

**Course:** Autonomous Systems  **Name / Roll No:** ______  **Date:** ______

## 1. Objective
Build a RAG-based academic helpdesk that answers questions about programs, courses, rules and the time table,
drafts emails to instructors, refuses out-of-scope questions, logs what it could not answer, and cites its sources.
Compare a single-agent and a multi-agent design, and two LLMs.

## 2. Knowledge base
| # | File | Type | What it contains |
|---|------|------|------------------|
| 1 | | pdf/csv/txt | |
| … | | | |

Total files: __ · Total chunks after ingestion: __ (from `python main.py ingest`)
Personal data (names, emails, roll numbers) was replaced with dummy values.

## 3. System design
- **Ingestion:** PDF page-wise text, TXT, CSV rows as `column: value` text (8 rows per chunk).
  Chunk size 600 chars, overlap 100, split on paragraph → sentence boundaries. The file name is prepended before embedding.
- **Embeddings / store:** `BAAI/bge-small-en-v1.5` (384-dim, normalised, query instruction prefix), ChromaDB with cosine distance.
- **Retrieval:** top-3 (passages capped at 700 chars); chunks below a cosine similarity of 0.50 are dropped, and if nothing is left the agent is told to refuse.
- **Tools:** `search_documents`, `lookup_course`, `count_courses`, `lookup_instructor_email`, `draft_email`, `log_unanswered_question`.
- **Agents:** (diagram) orchestrator → policy_agent / schedule_agent / email_agent (ADK `sub_agents` + `transfer_to_agent`).
- **LLM:** Llama 3.1 8B through Ollama (LiteLLM connector), temperature 0.2, num_ctx 8192.

## 4. Evaluation setup
30 questions (`evaluation/questions.json`): 11 policy, 6 schedule, 3 counting, 4 email, 6 out-of-scope.
Each configuration was run __ times with a fresh session per question. Accuracy is the keyword auto-check plus manual
grading of the rest (`manual_correct` in results.csv).

## 5. Results
| Metric | Single (Llama3.1) | Multi (Llama3.1) | Multi (Qwen3 / other) |
|---|---|---|---|
| Answer accuracy | | | |
| Correct refusals (out-of-scope) | | | |
| False refusals (in-scope) | | | |
| Answers with citation | | | |
| Grounded citations | | | |
| Correct tool | | | |
| Correct routing | – | | |
| Avg latency (s) | | | |

### Per-category accuracy
| Category | Single | Multi | Other LLM |
|---|---|---|---|
| policy | | | |
| schedule | | | |
| count | | | |
| email | | | |
| out_of_scope | | | |

## 6. Answers that changed across runs
| ID | Question | What changed (refusal ↔ answer, different number, different citation, wording only) |
|---|---|---|
| | | |

## 7. Error analysis
- Retrieval failures (the right chunk was not in the top-k):
- Generation failures (right chunk retrieved, wrong or partial answer):
- Routing failures (wrong specialist):
- Tool-calling failures (malformed arguments, tool not called):
- Contents of `logs/unanswered_questions.csv`:

## 8. Observations and conclusion
- Single vs multi agent:
- Effect of changing the LLM:
- Limitations (scanned PDFs, tables inside PDFs, exact codes in dense retrieval, 8B tool-calling reliability):
- Possible improvements (hybrid BM25 + dense search, re-ranker, metadata filters, larger model):
