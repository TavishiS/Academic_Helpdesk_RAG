# Evaluation summary: llama3.1-8b_multi_20261029_015341

- Mode: **multi**, model: **llama3.1:8b**, runs: 3, questions: 37
- Temperature: 0.2, top_k: 3, min_similarity: 0.5

| Metric | Value |
|---|---|
| Answer accuracy (auto, keyword-based) | 74.2% (n=66) |
| Correct refusals (out-of-scope) | 100.0% (n=18) |
| False refusals (in-scope) | 3.2% (n=93) |
| Answers with a citation | 100.0% (n=78) |
| Citations that match retrieved docs (grounded) | 100.0% (n=78) |
| Correct source cited (vs expected_sources) | 80.6% (n=72) |
| Correct tool used | 94.6% (n=111) |
| Correct routing to specialist agent | 94.6% (n=111) |
| Avg latency per question | 6.4s |
| Errors | 0 |

## Per category
| Category | Accuracy (auto) | Refused | Tool OK |
|---|---|---|---|
| count | 100.0% (n=6) | 0.0% (n=9) | 100.0% (n=9) |
| curriculum | 41.7% (n=24) | 11.1% (n=27) | 88.9% (n=27) |
| email | 100.0% (n=12) | 0.0% (n=12) | 100.0% (n=12) |
| out_of_scope | n/a | 100.0% (n=18) | 100.0% (n=18) |
| policy | 66.7% (n=9) | 0.0% (n=27) | 88.9% (n=27) |
| schedule | 100.0% (n=15) | 0.0% (n=18) | 100.0% (n=18) |

## Questions whose answers changed across runs (4)
- **P01** What is the attendance requirement to sit in the Major exam? (verdict changed: False, min text similarity: 0.55)
- **P07** What is the minimum CGPA below which a student is put on academic probation? (verdict changed: False, min text similarity: 0.47)
- **S05** When do the Major exams start this semester? (verdict changed: False, min text similarity: 0.71)
- **D04** What is the total number of credits in the M.Tech. Cyber-Physical Systems (CPS) program? (verdict changed: True, min text similarity: 0.98)

_24 answers have no expected_keywords: grade them by hand in the `manual_correct` column of results.csv._