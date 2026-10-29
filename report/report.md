# Academic Helpdesk Agent: Report

**Course:** Autonomous Systems

**Group members:** Tavishi Srivastava (B23CS1101), Shreekar Mane (B23CS1069), Ekta Saini (B23CS1018), Debadatta Sahoo (B23CM1013)

## 1. Introduction
We built a RAG-based academic helpdesk that answers questions about programs, course contents, rules and the time table, drafts leave and makeup-exam emails to instructors, refuses what it cannot answer from its documents, logs those questions for a human, and cites the document behind each answer. This report compares a single agent with a multi-agent version (an orchestrator that hands each question to a policy, a schedule or an email agent), each run with two local models, Llama 3.1 8B and Qwen3 8B. Every number below comes from the four evaluation runs stored in `results/`, computed from each run's `records.json`; the headline rows equal the numbers printed in the four `summary.md` files.

## 2. System and setup
**System.** Documents are split into chunks, embedded with `bge-small-en-v1.5` and stored in ChromaDB. For each question the agent retrieves the top 3 chunks with a similarity of at least 0.5 (`top_k`, `min_similarity` and the temperature of 0.2 are recorded in every `summary.md`). Exact facts such as slots, instructors, counts and email IDs are looked up in the CSV tables by tools, not through embeddings, because embeddings are poor at exact codes and cannot count. The agents have six tools: `search_documents`, `lookup_course`, `list_courses`, `lookup_instructor_email`, `draft_email` and `log_unanswered_question`. The program itself prints email drafts and course lists from the tool results, and replaces every refusal with one standard sentence, logging the question if the agent forgot to.

**Knowledge base.** 20 files: three PDFs with rules and policies (regulations, attendance, examinations), ten curriculum PDFs, five department timetables as CSV (CSE, electrical, mechanical, civil, humanities), `slot_system.csv` and `faculty_contacts.csv`, whose emails and phone numbers are fake. `civil.csv`, `mechanical.csv` and `slot_system.csv` were not returned by any tool in any evaluation record, so the questions say almost nothing about them.

**Evaluation.** 37 questions (9 policy, 9 curriculum, 6 schedule, 3 counting, 4 email and 6 out-of-scope questions) were answered three times by each of the four configurations, 444 answers in total, each in a fresh session. 23 questions have reference keywords and are graded automatically; eight in-scope questions (P02, P03, P05, P07, P08, P09, S05, C01) have none and are not graded. Accuracy is the share of answered questions containing the keywords, so refusals do not lower it; we therefore also report it with refusals counted as failures. The results do not record the hardware, the chunk size (code default 600/100 characters), `num_ctx` or the output limit.

## 3. Results
Table 1 gives the headline metrics. Table 2 counts a refusal as a failure, which is the fairer view of what a student would experience.

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

*Table 1: headline metrics, as printed in each `summary.md`.*

| | llama3.1 single | llama3.1 multi | qwen3 single | qwen3 multi |
|---|---|---|---|---|
| Keyword-checkable in-scope questions x runs | 69 | 69 | 69 | 69 |
| Keyword hit (correct) | 75.4% (52/69) | 71.0% (49/69) | 75.4% (52/69) | 58.0% (40/69) |
| Answered, keyword missing (wrong) | 24.6% (17/69) | 24.6% (17/69) | 20.3% (14/69) | 29.0% (20/69) |
| Refused | 0.0% (0/69) | 4.3% (3/69) | 4.3% (3/69) | 13.0% (9/69) |
| Keyword hit but no `Source:` line (no email draft, for draft_email questions) in the text | 0 | 0 | 6 | 6 |
| Keyword hit in an answer that starts with "Okay" (reasoning text) | 0 | 0 | 52 | 40 |

*Table 2: accuracy with refusals counted as failures.*

In single mode both models reach 75.4%. In multi mode Llama falls slightly to 71.0% and Qwen3 clearly to 58.0%. Qwen3's numbers need care: every one of its keyword hits comes from an answer that begins with its own reasoning text, and six hits per configuration carry no source line because the reply was cut off while it was still reasoning.

| Category | llama3.1 single | llama3.1 multi | qwen3 single | qwen3 multi |
|---|---|---|---|---|
| policy (9 q) | 66.7% (n=9) / 0.0% / 100.0% | 66.7% (n=9) / 0.0% / 88.9% | 66.7% (n=9) / 11.1% / 100.0% | 75.0% (n=8) / 25.9% / 85.2% |
| curriculum (9 q) | 48.1% (n=27) / 0.0% / 100.0% | 41.7% (n=24) / 11.1% / 88.9% | 54.2% (n=24) / 11.1% / 92.6% | 59.1% (n=22) / 18.5% / 77.8% |
| schedule (6 q) | 100.0% (n=15) / 0.0% / 83.3% | 100.0% (n=15) / 0.0% / 100.0% | 100.0% (n=15) / 11.1% / 83.3% | 100.0% (n=13) / 27.8% / 77.8% |
| count (3 q) | 100.0% (n=6) / 33.3% / 100.0% | 100.0% (n=6) / 0.0% / 100.0% | 100.0% (n=6) / 0.0% / 100.0% | 83.3% (n=6) / 11.1% / 88.9% |
| email (4 q) | 100.0% (n=12) / 0.0% / 100.0% | 100.0% (n=12) / 0.0% / 100.0% | 100.0% (n=12) / 0.0% / 100.0% | 27.3% (n=11) / 8.3% / 16.7% |
| out_of_scope (6 q) | n/a / 100.0% / 100.0% | n/a / 100.0% / 100.0% | n/a / 100.0% / 100.0% | n/a / 100.0% / 100.0% |

*Table 3: per category: accuracy among answered keyword questions / refusal rate / correct-tool rate.*

Schedule, counting and email questions are answered correctly in every configuration except by Qwen3 in multi mode: its email accuracy drops to 27.3% because it never reached the `draft_email` tool, its counting accuracy to 83.3%, and it refused 27.8% of the schedule records. The curriculum questions are the hardest (41.7% to 59.1%).

| | llama3.1 single | llama3.1 multi | qwen3 single | qwen3 multi |
|---|---|---|---|---|
| Out-of-scope refused | 100.0% (18/18) | 100.0% (18/18) | 100.0% (18/18) | 100.0% (18/18) |
| In-scope refused (false refusals) | 3.2% (3/93) | 3.2% (3/93) | 8.6% (8/93) | 20.4% (19/93) |
| Refusals where the log entry was added by the program, not the agent | 12 of 21 | 0 of 21 | 19 of 26 | 16 of 37 |

*Table 4: refusals.*

| | llama3.1 single | llama3.1 multi | qwen3 single | qwen3 multi |
|---|---|---|---|---|
| Explicit `Source:` line with a knowledge-base file | 98.7% (77/78) | 100.0% (78/78) | 78.1% (57/73) | 77.8% (49/63) |
| Correct source cited, as reported (questions with expected_sources) | 84.7% (61/72) | 80.6% (58/72) | 73.6% (53/72) | 74.6% (47/63) |
| Correct source cited, explicit `Source:` lines against the current expected_sources | 86.1% (62/72) | 80.6% (58/72) | 63.9% (46/72) | 63.5% (40/63) |
| Records where the scorer's `cited` set differs from the files on the `Source:` lines | 0 of 78 | 0 of 78 | 12 of 73 | 10 of 63 |

*Table 5: citations. "Explicit" uses only the `Source:` lines.*

Every out-of-scope question was refused in every configuration, and Table 4 shows how often an in-scope question was refused by mistake. Part of this reliability comes from the program: in 12 of Llama single's 21 refusals the agent did not call the log tool itself. Llama names a knowledge-base file on a `Source:` line in 98.7% to 100% of its answers, Qwen3 in about 78%. "Grounded" only means that the cited file was returned by a tool, not that the statement is in it.

| | llama3.1 single | llama3.1 multi | qwen3 single | qwen3 multi |
|---|---|---|---|---|
| Expected file among the retrieved files | 96.0% (72/75) | 88.0% (66/75) | 96.0% (72/75) | 77.3% (58/75) |
| Expected file missing: a tool returned a different file | 3 | 6 | 1 | 5 |
| Expected file missing: no search or lookup call (nothing returned) | 0 | 3 | 2 | 12 |
| …answered but keyword missing (right file retrieved, wrong or incomplete answer) | 17 | 17 | 12 | 7 |

*Table 6: was the expected document retrieved (file level; 75 records with an expected source).*

| | llama3.1 single | llama3.1 multi | qwen3 single | qwen3 multi |
|---|---|---|---|---|
| Mean | 5.6 | 6.4 | 41.1 | 43.4 |
| Median | 5.0 | 6.1 | 39.6 | 44.2 |
| Median answer length (characters) | 112 | 107 | 997 | 791 |
| Answers starting with "Okay" | 0 of 111 | 0 of 111 | 91 of 111 | 81 of 111 |

*Table 7: latency in seconds and answer style.*

The expected document was returned in 96.0% of the single-agent records, and in no record did a search run and come back empty. In the multi-agent runs, 15 of the 26 misses are records where no search or lookup was called at all. Llama answers in 5 to 6 seconds and Qwen3 in about 40, partly because Qwen3 writes seven to nine times more text. The hardware is not recorded and the two models ran at different times, so this is not a pure speed comparison.

| | llama3.1 single | llama3.1 multi | qwen3 single | qwen3 multi |
|---|---|---|---|---|
| Questions with a word-for-word identical answer in all 3 runs | 18 of 37 | 21 of 37 | 7 of 37 | 7 of 37 |
| Questions listed as changed in summary.md | 7 | 4 | 29 | 29 |
| …verdict changed | 1 | 1 | 6 | 17 |
| …only the wording changed (verdict identical) | 6 | 3 | 23 | 12 |

*Table 8: stability over the three runs.*

Llama is far more consistent between runs: only D02 (answers 18, 30, 30) and D04 (56, 12, 12) changed verdict, against 6 and 17 questions for Qwen3, whose wording also varies because of its reasoning text.

## 4. Error analysis
**Right document, wrong answer.** Table 6 shows that most wrong answers of the single agents come after the correct file was retrieved: 17 of Llama's 17 wrong answers and 12 of Qwen3's 14. P04, D05 and D08 were never answered correctly by any configuration. The two Llama cases we could inspect show two different causes: for D02 the search query was identical in all three runs yet the answers were 18, 30 and 30, which is sampling at temperature 0.2; for D09 the single agent always searched "grand total credits ..." and answered 108, 108, 90, while the multi agent searched "... credit total" and answered the correct 57 three times, so the wording of the query matters. The results store only the names of the retrieved files, not the retrieved text, so we cannot say whether the chunk with the answer was among the three.

**Wrong document.** For P02 (Open Elective credits) only `EE curriculum.pdf` was returned in 10 of 12 records and Llama answered 12, while the reference is 10. The question names no program, which may be why another curriculum ranked first.

**Routing.** In the multi-agent runs Llama sent P05 (the procedure for a makeup examination) to the email agent every time, which drafted a makeup email instead of describing the procedure, and sent D01 to the schedule agent, which refused without searching; the single agent answered D01 correctly. Qwen3 sent S04 to the policy agent every time.

**Qwen3's output.** 91 of 111 (single) and 81 of 111 (multi) Qwen3 answers begin with "Okay..." reasoning, against none for Llama, and 35 and 28 stop in the middle of a sentence. In multi mode E01, E03 and E04 never called `draft_email`. This is consistent with the 400-token output limit in the code, but that value is not recorded, so it remains an interpretation.

**Two questions where the reference is the problem.** All 12 answers to P04 give the "C grade" rule from `academic_regulations.pdf`, while the reference ("deregistration") comes from `attendance_policy.pdf`. For C01 every answered run reported 0 Humanities 400-level electives, but `humanities.csv` has no course-type column, so the filter "elective" can never match; C01 has no reference answer and is not graded.

**Limits of our scoring.** Accuracy excludes refusals; eight questions are ungraded; P01 and P02 listed two expected files in one string when the runs were scored, which the scorer cannot read (this has since been fixed); a file counts as cited if its name appears anywhere in the answer, which affects 22 Qwen3 records and none of Llama's; keywords are also searched in Qwen3's reasoning text; and three runs are too few for a significance test.

## 5. Conclusion
For Llama 3.1 8B the multi-agent design brought nothing in these runs: 75.4% single against 71.0% multi, with the gap explained by four questions (D01 lost three answers to a routing error, D02 and D04 lost three between them, D09 gained three), and a slightly higher latency (5.6 s against 6.4 s). For Qwen3 8B the single agent is clearly better (75.4% against 58.0%, with 8.6% against 20.4% false refusals), plausibly because the extra routing step gives a model that spends its output on reasoning more chances to run out before it reaches a tool. Overall Llama is the better fit for this helpdesk: equal in single mode, better in multi mode, more consistent, quicker and cleaner in its answers, while Qwen3 shows its reasoning to the student. Both models refuse and log every out-of-scope question, and both cite documents, although a citation shows that the file was retrieved, not that the answer is right.

What we could not show: accuracy covers 23 of 37 questions, chunk-level retrieval cannot be judged, and only the model and the architecture were varied. The next steps we would take are to store the retrieved passages, fix the scorer and re-run, grade the eight open questions, sharpen the routing for P05 and D01, limit Qwen3's reasoning, add a course-type column to `humanities.csv`, and record the hardware and chunk size with every run.
