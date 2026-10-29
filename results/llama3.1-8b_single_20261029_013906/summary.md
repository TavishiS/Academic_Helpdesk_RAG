# Evaluation summary: llama3.1-8b_single_20261029_013906

- Mode: **single**, model: **llama3.1:8b**, runs: 3, questions: 37
- Temperature: 0.2, top_k: 3, min_similarity: 0.5

| Metric | Value |
|---|---|
| Answer accuracy (auto, keyword-based) | 75.4% (n=69) |
| Correct refusals (out-of-scope) | 100.0% (n=18) |
| False refusals (in-scope) | 3.2% (n=93) |
| Answers with a citation | 98.7% (n=78) |
| Citations that match retrieved docs (grounded) | 98.7% (n=78) |
| Correct source cited (vs expected_sources) | 84.7% (n=72) |
| Correct tool used | 97.3% (n=111) |
| Avg latency per question | 5.6s |
| Errors | 0 |

## Per category
| Category | Accuracy (auto) | Refused | Tool OK |
|---|---|---|---|
| count | 100.0% (n=6) | 33.3% (n=9) | 100.0% (n=9) |
| curriculum | 48.1% (n=27) | 0.0% (n=27) | 100.0% (n=27) |
| email | 100.0% (n=12) | 0.0% (n=12) | 100.0% (n=12) |
| out_of_scope | n/a | 100.0% (n=18) | 100.0% (n=18) |
| policy | 66.7% (n=9) | 0.0% (n=27) | 100.0% (n=27) |
| schedule | 100.0% (n=15) | 0.0% (n=18) | 83.3% (n=18) |

## Questions whose answers changed across runs (7)
- **P05** What is the procedure to apply for a makeup examination? (verdict changed: False, min text similarity: 0.16)
- **P06** How many grade points does an A grade carry? (verdict changed: False, min text similarity: 0.7)
- **P09** Can a B.Tech. student register for a 700 level (PG) course? (verdict changed: False, min text similarity: 0.78)
- **S05** When do the Major exams start this semester? (verdict changed: False, min text similarity: 0.65)
- **D02** How many Programme Elective (PE) credits are there in the B.Tech. Bioengineering curriculum? (verdict changed: True, min text similarity: 0.99)
- **D03** What is the grand total of credits in the BS in Physics with Specialization program? (verdict changed: False, min text similarity: 0.59)
- **D08** What is the total credit requirement of the M.Sc. Mathematics program? (verdict changed: False, min text similarity: 0.39)

_21 answers have no expected_keywords: grade them by hand in the `manual_correct` column of results.csv._