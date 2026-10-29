# Evaluation summary: qwen3-8b_single_20261029_180824

- Mode: **single**, model: **qwen3:8b**, runs: 3, questions: 37
- Temperature: 0.2, top_k: 3, min_similarity: 0.5

| Metric | Value |
|---|---|
| Answer accuracy (auto, keyword-based) | 78.8% (n=66) |
| Correct refusals (out-of-scope) | 100.0% (n=18) |
| False refusals (in-scope) | 8.6% (n=93) |
| Answers with a citation | 90.4% (n=73) |
| Citations that match retrieved docs (grounded) | 89.0% (n=73) |
| Correct source cited (vs expected_sources) | 73.6% (n=72) |
| Correct tool used | 95.5% (n=111) |
| Avg latency per question | 41.1s |
| Errors | 0 |

## Per category
| Category | Accuracy (auto) | Refused | Tool OK |
|---|---|---|---|
| count | 100.0% (n=6) | 0.0% (n=9) | 100.0% (n=9) |
| curriculum | 54.2% (n=24) | 11.1% (n=27) | 92.6% (n=27) |
| email | 100.0% (n=12) | 0.0% (n=12) | 100.0% (n=12) |
| out_of_scope | n/a | 100.0% (n=18) | 100.0% (n=18) |
| policy | 66.7% (n=9) | 11.1% (n=27) | 100.0% (n=27) |
| schedule | 100.0% (n=15) | 11.1% (n=18) | 83.3% (n=18) |

## Questions whose answers changed across runs (29)
- **P01** What is the attendance requirement to sit in the Major exam? (verdict changed: False, min text similarity: 0.14)
- **P02** How many Open Elective credits do I need to earn in order to get a B.Tech. Degree? (verdict changed: False, min text similarity: 0.19)
- **P03** What is the total number of credits required for the B.Tech. degree? (verdict changed: False, min text similarity: 0.04)
- **P04** What happens if my attendance in a course is below the required minimum? (verdict changed: False, min text similarity: 0.11)
- **P05** What is the procedure to apply for a makeup examination? (verdict changed: False, min text similarity: 0.18)
- **P06** How many grade points does an A grade carry? (verdict changed: False, min text similarity: 0.17)
- **P08** What is the maximum number of credits a student can register for in a semester? (verdict changed: False, min text similarity: 0.24)
- **P09** Can a B.Tech. student register for a 700 level (PG) course? (verdict changed: False, min text similarity: 0.4)
- **S01** What is the slot for the course Autonomous Systems? (verdict changed: False, min text similarity: 0.56)
- **S02** Who is the instructor of CSL7650? (verdict changed: False, min text similarity: 0.58)
- **S03** In which slot is CSL3030 offered? (verdict changed: False, min text similarity: 0.42)
- **S04** How many credits is the course Autonomous Systems? (verdict changed: False, min text similarity: 0.48)
- **S05** When do the Major exams start this semester? (verdict changed: True, min text similarity: 0.02)
- **S06** At what time is the Autonomous Systems class held? (verdict changed: False, min text similarity: 0.43)
- **C01** How many 400 level electives have been floated by the Humanities department in this semester? (verdict changed: False, min text similarity: 0.33)
- **E01** Write an email to the course instructor of CSL7650 that I need leave for 2 days (verdict changed: False, min text similarity: 0.33)
- **E02** What is the email ID of the instructor of Autonomous Systems? (verdict changed: False, min text similarity: 0.3)
- **E03** Draft an email to the instructor of CSL3030 requesting a makeup exam because I missed the minor exam due to fever. (verdict changed: False, min text similarity: 0.51)
- **E04** I had viral fever for 3 days. Write a sick leave email to the instructor of Data Structures and Algorithms. (verdict changed: False, min text similarity: 0.41)
- **O06** What is the timing of the campus gym? (verdict changed: False, min text similarity: 0.39)
- **D01** Which specializations are offered in the B.Tech. AI & DS program? (verdict changed: False, min text similarity: 0.14)
- **D02** How many Programme Elective (PE) credits are there in the B.Tech. Bioengineering curriculum? (verdict changed: True, min text similarity: 0.01)
- **D03** What is the grand total of credits in the BS in Physics with Specialization program? (verdict changed: False, min text similarity: 0.31)
- **D04** What is the total number of credits in the M.Tech. Cyber-Physical Systems (CPS) program? (verdict changed: True, min text similarity: 0.06)
- **D05** How many credits is the B.Tech. Project SS499 in the B.Tech. Systems Science curriculum? (verdict changed: True, min text similarity: 0.01)
- **D06** How many Programme Core credits does the B.Tech. Electronics Engineering curriculum have? (verdict changed: False, min text similarity: 0.2)
- **D07** What is the total number of credits in the Integrated Teacher Education Program (ITEP)? (verdict changed: True, min text similarity: 0.06)
- **D08** What is the total credit requirement of the M.Sc. Mathematics program? (verdict changed: False, min text similarity: 0.32)
- **D09** What is the grand total of credits in the M.Tech. Data and Computational Sciences program? (verdict changed: True, min text similarity: 0.05)

_19 answers have no expected_keywords: grade them by hand in the `manual_correct` column of results.csv._