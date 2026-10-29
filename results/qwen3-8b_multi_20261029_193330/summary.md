# Evaluation summary: qwen3-8b_multi_20261029_193330

- Mode: **multi**, model: **qwen3:8b**, runs: 3, questions: 37
- Temperature: 0.2, top_k: 3, min_similarity: 0.5

| Metric | Value |
|---|---|
| Answer accuracy (auto, keyword-based) | 66.7% (n=60) |
| Correct refusals (out-of-scope) | 100.0% (n=18) |
| False refusals (in-scope) | 20.4% (n=93) |
| Answers with a citation | 88.9% (n=63) |
| Citations that match retrieved docs (grounded) | 84.1% (n=63) |
| Correct source cited (vs expected_sources) | 74.6% (n=63) |
| Correct tool used | 77.5% (n=111) |
| Correct routing to specialist agent | 92.8% (n=111) |
| Avg latency per question | 43.4s |
| Errors | 0 |

## Per category
| Category | Accuracy (auto) | Refused | Tool OK |
|---|---|---|---|
| count | 83.3% (n=6) | 11.1% (n=9) | 88.9% (n=9) |
| curriculum | 59.1% (n=22) | 18.5% (n=27) | 77.8% (n=27) |
| email | 27.3% (n=11) | 8.3% (n=12) | 16.7% (n=12) |
| out_of_scope | n/a | 100.0% (n=18) | 100.0% (n=18) |
| policy | 75.0% (n=8) | 25.9% (n=27) | 85.2% (n=27) |
| schedule | 100.0% (n=13) | 27.8% (n=18) | 77.8% (n=18) |

## Questions whose answers changed across runs (29)
- **P01** What is the attendance requirement to sit in the Major exam? (verdict changed: False, min text similarity: 0.11)
- **P02** How many Open Elective credits do I need to earn in order to get a B.Tech. Degree? (verdict changed: False, min text similarity: 0.57)
- **P03** What is the total number of credits required for the B.Tech. degree? (verdict changed: False, min text similarity: 0.06)
- **P04** What happens if my attendance in a course is below the required minimum? (verdict changed: True, min text similarity: 0.06)
- **P05** What is the procedure to apply for a makeup examination? (verdict changed: True, min text similarity: 0.07)
- **P06** How many grade points does an A grade carry? (verdict changed: False, min text similarity: 0.2)
- **P07** What is the minimum CGPA below which a student is put on academic probation? (verdict changed: True, min text similarity: 1.0)
- **P08** What is the maximum number of credits a student can register for in a semester? (verdict changed: False, min text similarity: 0.16)
- **P09** Can a B.Tech. student register for a 700 level (PG) course? (verdict changed: True, min text similarity: 0.06)
- **S01** What is the slot for the course Autonomous Systems? (verdict changed: False, min text similarity: 0.47)
- **S02** Who is the instructor of CSL7650? (verdict changed: True, min text similarity: 0.08)
- **S03** In which slot is CSL3030 offered? (verdict changed: False, min text similarity: 0.54)
- **S04** How many credits is the course Autonomous Systems? (verdict changed: True, min text similarity: 0.04)
- **C01** How many 400 level electives have been floated by the Humanities department in this semester? (verdict changed: True, min text similarity: 0.02)
- **C02** How many elective courses are offered by the Computer Science department this semester? (verdict changed: True, min text similarity: 0.1)
- **E01** Write an email to the course instructor of CSL7650 that I need leave for 2 days (verdict changed: True, min text similarity: 0.1)
- **E02** What is the email ID of the instructor of Autonomous Systems? (verdict changed: True, min text similarity: 0.01)
- **E03** Draft an email to the instructor of CSL3030 requesting a makeup exam because I missed the minor exam due to fever. (verdict changed: False, min text similarity: 0.15)
- **E04** I had viral fever for 3 days. Write a sick leave email to the instructor of Data Structures and Algorithms. (verdict changed: False, min text similarity: 0.24)
- **O05** Which laptop should I buy for programming? (verdict changed: False, min text similarity: 0.14)
- **D01** Which specializations are offered in the B.Tech. AI & DS program? (verdict changed: True, min text similarity: 0.04)
- **D02** How many Programme Elective (PE) credits are there in the B.Tech. Bioengineering curriculum? (verdict changed: False, min text similarity: 0.43)
- **D03** What is the grand total of credits in the BS in Physics with Specialization program? (verdict changed: False, min text similarity: 0.17)
- **D04** What is the total number of credits in the M.Tech. Cyber-Physical Systems (CPS) program? (verdict changed: True, min text similarity: 0.02)
- **D05** How many credits is the B.Tech. Project SS499 in the B.Tech. Systems Science curriculum? (verdict changed: True, min text similarity: 0.05)
- **D06** How many Programme Core credits does the B.Tech. Electronics Engineering curriculum have? (verdict changed: True, min text similarity: 0.02)
- **D07** What is the total number of credits in the Integrated Teacher Education Program (ITEP)? (verdict changed: True, min text similarity: 0.08)
- **D08** What is the total credit requirement of the M.Sc. Mathematics program? (verdict changed: True, min text similarity: 0.08)
- **D09** What is the grand total of credits in the M.Tech. Data and Computational Sciences program? (verdict changed: True, min text similarity: 0.01)

_14 answers have no expected_keywords: grade them by hand in the `manual_correct` column of results.csv._