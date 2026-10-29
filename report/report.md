# Academic Helpdesk Agent: Report

**Course:** Autonomous Systems

**Group members**

`Tavishi Srivastava (B23CS1101)`
`Shreekar Mane (B23CS1069)`
`Ekta Saini (B23CS1018)`
`Debadatta Sahoo (B23CM1013)`

> Every number comes from the four evaluation runs in `results/` (Llama 3.1 8B and Qwen3 8B, each as a single agent and as a multi-agent system; 37 questions x 3 runs). `report/analyze_results.py` recomputes them and checks them against the four `summary.md` files. What the results do not record (hardware, chunk size, `num_ctx`, output limit) is marked as such. The long version with all tables is `report/report_full.md`.

## 1. System
**Pipeline.** PDFs are read page by page (page number kept for citations). Timetable CSVs, which are messy exports (repeated headers, section titles, co-instructors), are parsed into `Label: value` lines; the weekly slot grid becomes `Slot E: Tue 11:00-11:50` lines. Text is split into paragraph/sentence chunks with overlap (code default 600/100 characters; **the chunk size used in the runs is not recorded**). Each chunk is embedded as `Document: <title>` + text with `BAAI/bge-small-en-v1.5` into ChromaDB (cosine); queries get the bge instruction prefix. Recorded in every `summary.md`: `top_k` 3, `min_similarity` 0.5, temperature 0.2. Exact facts (slots, counts, instructors, emails) are looked up in the CSV tables by tools, not by embeddings.
**Tools (6).** `search_documents` (RAG), `lookup_course`, `list_courses`, `lookup_instructor_email`, `draft_email` (fixed template, never sent), `log_unanswered_question`.
**Agents.** *Single:* one agent with all tools. *Multi:* `helpdesk_orchestrator` routes (ADK `transfer_to_agent`) to `policy_agent`, `schedule_agent` or `email_agent`, each with only its own tools; the orchestrator refuses non-academic questions itself.
**Program safeguards (`session.py`), which decide what the student sees.** Email drafts and course lists are printed by the program from tool results; if the LLM's reply is only a `Source:` line, the tool's summary sentence is put in front; every refusal is replaced by one standard sentence, and the program logs the question if the agent did not.

## 2. Knowledge base: 20 files (13 PDF, 7 CSV)
| Group | Files (number of evaluation records, of 444, in which a tool returned the file) |
|---|---|
| Rules and policies (3 PDF) | academic_regulations (117), attendance_policy (23), exams_policy (14) |
| Curricula (10 PDF) | cse_curriculum (2), AI&DS (8), B.Tech. Bioengineering (12), BS Physics (12), B.Tech. Systems Science "Curriculum for B.Tech. Programs" (26), EE curriculum (36), M.Tech. CPS (13), M.Tech. Data and Computational Sciences "MTech Structure" (11), ITEP (10), M.Sc. Mathematics (12) |
| Timetables (5 CSV) | cse (109), electrical (12), humanities (12), mechanical (0), civil (0); the department is taken from the file name |
| Other (2 CSV) | slot_system (0), faculty_contacts (48): generated, emails on the reserved `.example` domain, phone numbers starting 2-5, so none is real |

`civil.csv`, `mechanical.csv` and `slot_system.csv` were not returned in any record, so the question set says almost nothing about them. The number of chunks is not recorded.

## 3. Evaluation setup
**Questions (37):** policy P01-P09 (9), curriculum D01-D09 (9), schedule S01-S06 (6), count C01-C03 (3), email E01-E04 (4), out-of-scope O01-O06 (6, refusal expected). 23 have `expected_keywords`; **8 in-scope questions have none** (P02, P03, P05, P07, P08, P09, S05, C01), are not graded, and `manual_correct` is empty in all runs. **Runs:** 4 configurations x 3 runs x 37 questions = 444 answers, a fresh session per question (Llama started 01:39 and 01:53, Qwen3 18:08 and 19:33 on the same day).
**Metrics (`run_eval.py`).** *Accuracy:* all keywords present, among questions that were answered (refusals excluded). *Correct / false refusal:* out-of-scope / in-scope questions refused. *Citation:* has one; grounded (cited file was returned by a tool); correct source. *Correct tool* and *routing* (expected specialist received the question). *Stability:* verdict (refused, keyword hit, expected tool) differs between runs, or text similarity below 0.8.
**Limits of the scoring.** (1) Accuracy excludes refusals, so Table 2 also counts them as failures. (2) Eight questions are ungraded. (3) When the runs were scored, `expected_sources` of P01 and P02 were written `a.pdf|b.pdf`, which the scorer cannot read, so those two could never count as a correct source (the file has since been changed to one source each). (4) A file counts as cited if its name without extension appears anywhere in the answer; this changes nothing for Llama (0 records) but 22 records for Qwen3, whose reasoning text mentions file names. (5) Keywords are searched in the whole text, including Qwen3's reasoning. (6) The tool check is strict: S02 counts as a miss in both single runs although the answers were correct. (7) Three runs, no significance test.

## 4. Results
| Metric | llama3.1 single | llama3.1 multi | qwen3 single | qwen3 multi |
|---|---|---|---|---|
| Answer accuracy (auto, keyword-based) | 75.4% (n=69) | 74.2% (n=66) | 78.8% (n=66) | 66.7% (n=60) |
| Correct refusals (out-of-scope) | 100.0% (n=18) | 100.0% (n=18) | 100.0% (n=18) | 100.0% (n=18) |
| False refusals (in-scope) | 3.2% (n=93) | 3.2% (n=93) | 8.6% (n=93) | 20.4% (n=93) |
| Answers with a citation | 98.7% (n=78) | 100.0% (n=78) | 90.4% (n=73) | 88.9% (n=63) |
| Citations that match retrieved docs (grounded) | 98.7% (n=78) | 100.0% (n=78) | 89.0% (n=73) | 84.1% (n=63) |
| Correct source cited (vs expected_sources) | 84.7% (n=72) | 80.6% (n=72) | 73.6% (n=72) | 74.6% (n=63) |
| Correct tool used | 97.3% (n=111) | 94.6% (n=111) | 95.5% (n=111) | 77.5% (n=111) |
| Avg latency per question | 5.6s | 6.4s | 41.1s | 43.4s |
| Correct routing to specialist agent | n/a (single mode) | 94.6% (n=111) | n/a (single mode) | 92.8% (n=111) |

*Table 1: headline metrics as printed in each `summary.md`.*

| | llama3.1 single | llama3.1 multi | qwen3 single | qwen3 multi |
|---|---|---|---|---|
| Keyword-checkable in-scope questions x runs | 69 | 69 | 69 | 69 |
| Keyword hit (correct) | 75.4% (52/69) | 71.0% (49/69) | 75.4% (52/69) | 58.0% (40/69) |
| Answered, keyword missing (wrong) | 24.6% (17/69) | 24.6% (17/69) | 20.3% (14/69) | 29.0% (20/69) |
| Refused | 0.0% (0/69) | 4.3% (3/69) | 4.3% (3/69) | 13.0% (9/69) |
| Keyword hit but no `Source:` line (no email draft, for draft_email questions) in the text | 0 | 0 | 6 | 6 |
| Keyword hit in an answer that starts with "Okay" (reasoning text) | 0 | 0 | 52 | 40 |

*Table 2: accuracy counting refusals as failures.*

The accuracy in Table 1 leaves out refusals; Table 2 counts them. **Every keyword hit of Qwen3 comes from an answer that begins with its own reasoning text** (52 of 52, 40 of 40), and 6 hits per Qwen3 configuration have no `Source:` line or email draft: the reply ends before a final answer, mostly in mid-sentence (e.g. qwen3 single P01 run 1 ends "...The user might be").

| Category | llama3.1 single | llama3.1 multi | qwen3 single | qwen3 multi |
|---|---|---|---|---|
| policy (9 q) | 66.7% (n=9) / 0.0% / 100.0% | 66.7% (n=9) / 0.0% / 88.9% | 66.7% (n=9) / 11.1% / 100.0% | 75.0% (n=8) / 25.9% / 85.2% |
| curriculum (9 q) | 48.1% (n=27) / 0.0% / 100.0% | 41.7% (n=24) / 11.1% / 88.9% | 54.2% (n=24) / 11.1% / 92.6% | 59.1% (n=22) / 18.5% / 77.8% |
| schedule (6 q) | 100.0% (n=15) / 0.0% / 83.3% | 100.0% (n=15) / 0.0% / 100.0% | 100.0% (n=15) / 11.1% / 83.3% | 100.0% (n=13) / 27.8% / 77.8% |
| count (3 q) | 100.0% (n=6) / 33.3% / 100.0% | 100.0% (n=6) / 0.0% / 100.0% | 100.0% (n=6) / 0.0% / 100.0% | 83.3% (n=6) / 11.1% / 88.9% |
| email (4 q) | 100.0% (n=12) / 0.0% / 100.0% | 100.0% (n=12) / 0.0% / 100.0% | 100.0% (n=12) / 0.0% / 100.0% | 27.3% (n=11) / 8.3% / 16.7% |
| out_of_scope (6 q) | n/a / 100.0% / 100.0% | n/a / 100.0% / 100.0% | n/a / 100.0% / 100.0% | n/a / 100.0% / 100.0% |

*Table 3: per category: accuracy among answered keyword questions / refusal rate / correct-tool rate.*

**Tools and routing.** Expected tool not called: Llama single 3 of 111 (S02 x3), Llama multi 6 (D01 x3, P05 x3), Qwen3 single 5, Qwen3 multi 25 (E01, E03, E04 never reached `draft_email`). Wrong or missing routing: Llama multi 6 of 111 (94.6% correct), Qwen3 multi 8 of 111 (92.8% correct).
**Refusals.** All 18 out-of-scope records were refused in every configuration. In-scope records refused: 3, 3, 8 and 19 of 93. In 12 of Llama single's 21 refusals and 19 of Qwen3 single's 26 the agent did not call the log tool; the program added the entry (0 of 21 for Llama multi, 16 of 37 for Qwen3 multi). For Qwen3, 10 refused out-of-scope records show reasoning text ("Okay, ...") instead of the standard sentence.

| | llama3.1 single | llama3.1 multi | qwen3 single | qwen3 multi |
|---|---|---|---|---|
| Explicit `Source:` line with a knowledge-base file | 98.7% (77/78) | 100.0% (78/78) | 78.1% (57/73) | 77.8% (49/63) |
| Correct source cited, as reported (questions with expected_sources) | 84.7% (61/72) | 80.6% (58/72) | 73.6% (53/72) | 74.6% (47/63) |
| Correct source cited, explicit `Source:` lines against the current expected_sources | 86.1% (62/72) | 80.6% (58/72) | 63.9% (46/72) | 63.5% (40/63) |
| Records where the scorer's `cited` set differs from the files on the `Source:` lines | 0 of 78 | 0 of 78 | 12 of 73 | 10 of 63 |

*Table 4: citations. "Explicit" uses only the `Source:` lines and compares them with the current `expected_sources`. "Grounded" only means the cited file was returned by a tool, not that the statement is in the passage.*

| | llama3.1 single | llama3.1 multi | qwen3 single | qwen3 multi |
|---|---|---|---|---|
| Expected file among the retrieved files | 96.0% (72/75) | 88.0% (66/75) | 96.0% (72/75) | 77.3% (58/75) |
| Expected file missing: a tool returned a different file | 3 | 6 | 1 | 5 |
| Expected file missing: no search or lookup call (nothing returned) | 0 | 3 | 2 | 12 |
| …answered but keyword missing (right file retrieved, wrong or incomplete answer) | 17 | 17 | 12 | 7 |

*Table 5: was the expected document retrieved (file level), of 75 records with an expected source. The retrieved text is not stored, so chunk level cannot be judged.*

| | llama3.1 single | llama3.1 multi | qwen3 single | qwen3 multi |
|---|---|---|---|---|
| Mean | 5.6 | 6.4 | 41.1 | 43.4 |
| Median | 5.0 | 6.1 | 39.6 | 44.2 |
| Median answer length (characters) | 112 | 107 | 997 | 791 |
| Answers starting with "Okay" | 0 of 111 | 0 of 111 | 91 of 111 | 81 of 111 |

*Table 6: latency in seconds and answer style. The first question of the first run was slow (Llama single 66.6 s), probably model loading. Hardware is not recorded and the runs were made at different times, so the model difference is not a pure speed comparison.*

## 5. Answers that changed across runs
| | llama3.1 single | llama3.1 multi | qwen3 single | qwen3 multi |
|---|---|---|---|---|
| Questions with a word-for-word identical answer in all 3 runs | 18 of 37 | 21 of 37 | 7 of 37 | 7 of 37 |
| Questions listed as changed in summary.md | 7 | 4 | 29 | 29 |
| …verdict changed | 1 | 1 | 6 | 17 |
| …only the wording changed (verdict identical) | 6 | 3 | 23 | 12 |

*Table 7: stability. Qwen3's wording changes are dominated by its reasoning text.*

Only **D02** (Llama single: 18, 30, 30) and **D04** (Llama multi: 56, 12, 12) changed verdict for Llama; D03 gave 29, 69, "not explicitly mentioned", D08 "not explicitly mentioned", 38, 38, and S05 and P05 changed wording (no reference answer; P07 gives 5.0 in single mode and "not explicitly stated" in multi mode). For D02 the search query was identical in all three runs, so the change comes from the LLM's sampling. For D09 the single agent always searched "grand total credits ..." and answered 108, 108, 90, while the multi agent always searched "... credit total" and answered the reference 57 three times: query wording matters. Qwen3 changed verdict on 6 (single) and 17 (multi) questions, e.g. E01 multi (✗✓✗) or S02 multi (✓R✓).

## 6. Error analysis
- **Retrieval (file level).** The expected file was returned in 96.0% of single-agent records. The clearest wrong-document case is **P02**: in 10 of 12 records only `EE curriculum.pdf` was returned, Llama answered "12" six times, the reference is 10 (expected source `academic_regulations.pdf`); the question names no program. Every other miss is a record in which no search or lookup was called (Table 5).
- **Generation (right file, wrong answer):** 17, 17, 12 and 7 records. Never correct in any configuration: **P04, D05, D08** (0 of 12); D09 (3), D02 (4), D03 (6). D05: Llama said 22 credits in all six runs (reference 7). P04: all 12 answers lack "deregistration" and give the "C grade" rule from `academic_regulations.pdf`, while the reference comes from `attendance_policy.pdf`.
- **Routing (multi):** P05 ("procedure to apply for a makeup examination") went to `email_agent` x3 and a makeup email was drafted; D01 went to `schedule_agent` x3 and was refused without searching (the single agent answered it x3). Qwen3 sent S04 to `policy_agent` x3 and answered D01 (x2), D05 and E03 without transferring.
- **Qwen3 format and tool calls.** 91 of 111 (single) and 81 of 111 (multi) answers begin with "Okay..." reasoning (none for Llama); 35 and 28 do not end with punctuation, a file name or a draft footer; the 2 and 13 records without any tool call are 1,640-2,123 characters and stop mid-sentence. This is consistent with the 400-token output limit in `config.py` (an interpretation; the value used is not recorded). In multi mode no email draft was produced (email accuracy 27.3% against 100% in single mode).
- **C01 is a data limit.** Every answered run reported 0 Humanities 400-level electives, but `humanities.csv` has no course-type column, so "elective" cannot match (8 of its 38 courses have a level-4 code; checked on the file, not from the results). C01 has no reference answer and is not graded.

## 7. Conclusion
- **Single vs multi.** *Llama:* no real difference (75.4% vs 71.0% counting refusals; false refusals 3.2% both; correct tools 97.3% vs 94.6%; mean latency 5.6 s vs 6.4 s); the gap is D01 (-3), D02 (-1), D04 (-2), D09 (+3). *Qwen3:* single is clearly better (75.4% vs 58.0%; false refusals 8.6% vs 20.4%; correct tools 95.5% vs 77.5%). The multi-agent design added routing errors and, in these runs, no accuracy gain.
- **Llama vs Qwen3.** Equal in single mode (75.4%); Llama is better in multi mode, cites reliably (explicit `Source:` in 98.7-100% of answers against 77.8-78.1%), is far more stable (18-21 of 37 questions identical in all runs against 7) and answers in 5-6 s against about 40 s. Qwen3's reasoning text is shown to the student.
- **Refusing and citing.** All out-of-scope questions were refused and logged; part of that reliability comes from the program's own logging. Every citation Llama wrote named a file the tools had returned, which shows retrieval of that file, not correctness.
- **Not shown by the results.** Accuracy covers 23 of 37 questions; whether the answer passage was among the retrieved chunks cannot be decided; only the model and architecture were varied.
- **Next steps (not evaluated).** Store retrieved passages; fix the scorer (citations on `Source:` lines only, final answer instead of reasoning) and re-run with the corrected P01/P02 sources; fill and grade the eight questions and add questions on `civil.csv`, `mechanical.csv`, `slot_system.csv`; sharpen routing for P05 and D01; limit Qwen3's reasoning or raise its output limit; add a course-type column to `humanities.csv`; record hardware, chunk size, `num_ctx` and output limit.
