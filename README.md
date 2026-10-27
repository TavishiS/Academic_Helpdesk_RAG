# Academic Helpdesk Agent (RAG + Multi-Agent)

Autonomous Systems assignment. This is a local academic helpdesk that answers questions about academic programs,
course contents, rules and regulations and the time table, and drafts emails to course instructors (for sick leave or
makeup exams). Every answer cites the document it came from. Out-of-scope questions get an *"I don't know"* reply and
are logged so a human can answer them later.

Everything runs locally on a 16 GB laptop:

| Component | Choice |
|---|---|
| Agent framework | Google ADK (`google-adk`) |
| LLM | Llama 3.1 8B via Ollama, connected through ADK's LiteLLM connector |
| Embeddings | `BAAI/bge-small-en-v1.5` (HuggingFace, sentence-transformers, CPU) |
| Vector store | ChromaDB (persistent, cosine distance) |
| Knowledge base | `.pdf`, `.txt`, `.csv` files in `data/knowledge_base/` |

---
## Loading the model:

```bash
ollama run llama3.1:8b --keepalive 2h ""     # keep it loaded for the next 2 hours
ollama stop llama3.1:8b                       # free the RAM when you're done
```
## 1. How it works

```
                      ┌──────────────────────────┐
  student question ─▶ │  helpdesk_orchestrator   │── out of scope ─▶ "I don't know" + log_unanswered_question
                      └──────────┬───────────────┘
              transfer_to_agent  │
        ┌────────────────────────┼─────────────────────────┐
        ▼                        ▼                         ▼
  policy_agent             schedule_agent              email_agent
  rules, credits,          slots, instructors,         instructor email,
  attendance, curriculum   counting electives          leave / makeup drafts
        │                        │                         │
  search_documents         lookup_course              lookup_instructor_email
  (RAG over ChromaDB)      count_courses              draft_email
                           search_documents
```

**RAG pipeline (`helpdesk/ingest.py`, `helpdesk/retriever.py`)**
1. **Load:** PDFs page by page (the page number is kept for citations), TXT as is, and CSVs row by row with each row
   turned into `column: value | column: value` text. A raw CSV row means little to an embedding model.
2. **Chunk:** text is split on paragraphs, then sentences, and packed into chunks of about 600 characters with
   100 characters of overlap, so a rule that crosses a chunk boundary can still be found. CSVs get 8 rows per chunk.
3. **Embed:** `bge-small-en-v1.5` with normalised vectors. The file name is prepended to each chunk before embedding
   (e.g. `Document: attendance policy`) because file names carry a lot of meaning. Queries get the bge
   instruction prefix (`Represent this sentence for searching relevant passages:`), which bge models are trained with.
4. **Store / retrieve:** ChromaDB with cosine distance, top-3 chunks. Chunks with similarity below `MIN_SIMILARITY`
   (0.50) are thrown away. If nothing is left, the tool tells the agent to refuse, which is the first defence
   against hallucination.

**Why there are CSV tools as well as RAG (`helpdesk/csv_store.py`).** Dense embeddings are bad at exact strings like
`CSL7570`, and they cannot count ("how many 400-level electives…"). So every CSV in the knowledge base is also loaded
as a pandas table. Column names are matched through aliases (`Course Code` / `code` / `course_id` …), so the file
format can vary. A CSV with a course-code column is treated as a **course/timetable table**, and one with an email
column and a name column as the **faculty directory**.

**Tools (`helpdesk/tools.py`)**

| Tool | Used for |
|---|---|
| `search_documents(query)` | RAG search over all documents |
| `lookup_course(course)` | slot, instructor, credits… by course code or (fuzzy) name |
| `count_courses(department, level, course_type)` | "how many X electives" questions (level = first digit of the code number) |
| `lookup_instructor_email(course_code)` | course → instructor (timetable) → email (faculty CSV) |
| `draft_email(course_code, request_type, reason, dates)` | builds a leave / makeup-exam email draft (**never sent**) |
| `log_unanswered_question(question, reason)` | appends to `logs/unanswered_questions.csv` for human follow-up |

All tool arguments are plain required strings. 8B models fill these far more reliably than optional or nested
parameters.

**Two architectures** (`helpdesk/agents.py`), so they can be compared:
- `single`: one agent with all six tools.
- `multi`: the orchestrator routes to three specialists (ADK `sub_agents`, LLM-driven `transfer_to_agent`).

---

## 2. Project structure

```
AS_assignment/
├── Makefile                 human-friendly commands (make help)
├── main.py                  CLI: ingest / chat / ask
├── config.py                all settings (defaults, read from .env)
├── .env.example             copy to .env (make venv does it)
├── requirements.txt
├── scripts/
│   ├── install_requirements.py  installs only missing/outdated packages
│   ├── preflight.py             Ollama / model / index checks (make doctor)
│   └── smoke_test.py            make smoke-test
├── helpdesk/
│   ├── ingest.py            load → chunk → embed → ChromaDB
│   ├── retriever.py         embedding model + similarity search
│   ├── csv_store.py         structured lookups over CSVs
│   ├── tools.py             ADK tools
│   ├── agents.py            single + multi agent definitions
│   └── session.py           ADK Runner wrapper (answer + tool trace)
├── evaluation/
│   ├── questions.json       30 test prompts
│   └── run_eval.py          metrics + run-to-run stability
├── data/
│   ├── knowledge_base/      ← put your ~30 documents here
│   └── sample/              tiny DUMMY files for a smoke test
├── report/report_template.md
├── logs/                    unanswered_questions.csv
├── results/                 evaluation outputs
└── chroma_db/               created by ingest
```

---

## 3. Quick start (all through `make`)

You don't need to activate the venv or type long Python commands. Every `make` command prints what it is doing.

```bash
make venv              # 1. create .venv, install ONLY the missing requirements, create .env
make doctor            # 2. check Ollama is running, the model is pulled, the KB and the index
make pull-model        #    (only if doctor says the model is missing)
make smoke-test        # 3. end-to-end test on the dummy sample data
#    put your documents in data/knowledge_base/
make ingest            # 4. build the vector index from your documents
make chat single_agent # 5. chat with the single-agent helpdesk
make chat multi_agent  #    chat with the multi-agent helpdesk
```
Run `make` or `make help` to see every command.

| Command | What it does |
|---|---|
| `make venv` | creates `.venv/` if it doesn't exist, checks every package in `requirements.txt` and installs only those that are missing or outdated, then creates `.env` from `.env.example` |
| `make venv TORCH=cpu` | same, but installs the much smaller CPU-only PyTorch (laptops without an NVIDIA GPU) |
| `make doctor` | checks the Ollama server, the LLM model, the number of KB files and indexed chunks, and prints the active settings |
| `make pull-model` | `ollama pull` of the model in `.env` (or `MODEL=qwen3:8b`) |
| `make ingest` | load → chunk → embed → store the files in `KB_DIR` |
| `make chat single_agent` / `make chat multi_agent` | interactive chat (`new` = fresh session, `exit` = quit); add `TRACE=1` to see tool calls |
| `make ask Q="..."` | one question with its tool trace (add `single_agent` to use the single agent) |
| `make smoke-test` | ingest the sample data, test retrieval, test every tool, then ask 5 questions to both architectures (`make smoke-test multi_agent` for one only) |
| `make eval single_agent` / `make eval multi_agent` | evaluation (options: `RUNS=3`, `MODEL=qwen3:8b`, `IDS=P01,S01`) |
| `make eval-all` | evaluates both architectures |
| `make unanswered` | shows the logged questions that need a human answer |
| `make clean` | deletes the vector indexes and caches (documents, logs and results are kept) |

Prerequisites: Python 3.10+ and [Ollama](https://ollama.com) (`ollama serve` must be running). The first ingest
downloads `BAAI/bge-small-en-v1.5` (~130 MB) from HuggingFace and caches it.

### Settings: `.env`
`make venv` copies `.env.example` to `.env`. Edit `.env` to change the knowledge base folder, the model and so on:
```ini
KB_DIR=data/knowledge_base
LLM_MODEL=llama3.1:8b
TOP_K=3
MIN_SIMILARITY=0.50
```
A variable set in the shell wins over `.env` for a single run, e.g. `LLM_MODEL=qwen3:8b make chat multi_agent`.
The smoke test always uses `data/sample/` with its own index (`chroma_db_sample/`) and log, whatever `.env` says,
so it never overwrites your real index.

<details><summary>Without make (plain Python commands)</summary>

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python main.py ingest
python main.py chat --mode single          # or --mode multi, add --trace
python main.py ask "What is the slot for the course Autonomous Systems?" --trace
python scripts/smoke_test.py
python evaluation/run_eval.py --mode multi --runs 3 [--model qwen3:8b]
```
</details>

---

## 4. Adding the knowledge base

Put your files (`.pdf`, `.txt`, `.csv`) in `data/knowledge_base/`. Subfolders are fine. Suggested ~30 documents:

| Kind | Format | Examples |
|---|---|---|
| Rules & regulations | PDF | UG/PG academic regulations, attendance policy, grading policy, makeup exam rules |
| Programs / curriculum | PDF | B.Tech. curriculum & credit structure per branch, course descriptions |
| Office orders / circulars | PDF/TXT | recent academic office orders, registration notices |
| Academic calendar | PDF | semester calendar (add/drop dates, exam dates) |
| Time table / courses floated | **CSV** | `Course Code, Course Name, Department, Type, Credits, Slot, Instructor` |
| Faculty directory | **CSV** | `Name, Department, Email` (dummy emails are fine) |
| Slot definitions | CSV/TXT | which days/times make up slot A, B, … |

**CSV tips (important for the lookup tools)**
- The timetable CSV needs a course-code column. These columns are recognised (case-insensitive): `course code / code /
  course id`, `course name / title`, `instructor / faculty`, `slot`, `department / dept`, `type / category`, `credits`.
- For `count_courses`, include a `Type` column (Core/Elective/Open Elective…) and ideally a `Department` column.
- The faculty CSV needs a `Name` and an `Email` column. Instructor names should be spelled the same as in the timetable.
- Look at `data/sample/` for the exact format.

**PDF tips:** scanned PDFs have no text layer and will be skipped. Run OCR on them first or convert them to TXT.
Tables inside PDFs come out as messy text, so if the time table is a PDF, also save it as a CSV.

Then build the index (run this again whenever you add or change files):
```bash
make ingest
```
It prints how many chunks each file produced. A PDF with 0 chunks is probably scanned.

---

## 5. Running

```bash
make chat single_agent                 # single-agent baseline
make chat multi_agent                  # orchestrator + 3 specialists
make chat multi_agent TRACE=1          # also print which tools were called
make chat multi_agent MODEL=qwen3:8b   # another model (pull it first: make pull-model MODEL=qwen3:8b)

make ask Q="What is the slot for the course Autonomous Systems?"
make ask Q="Write an email to the course instructor of CSL7570 that I need leave for 2 days"
make ask Q="What are the available dining options on the campus?" single_agent
make unanswered                        # questions logged for a human
```
Before starting, `chat`, `ask` and `eval` check that Ollama is running, the model is pulled and the index exists,
and tell you which `make` command fixes anything that is missing.

### Smoke test
```bash
make smoke-test               # both architectures
make smoke-test multi_agent   # only one (faster)
```
It runs in 4 steps, printing PASS/FAIL for each check:
1. Ingest `data/sample/` into a separate `chroma_db_sample/` index.
2. Retrieval: the attendance query must return the sample rules file as the top hit, above `MIN_SIMILARITY`.
3. Tools, called directly without the LLM: the course slot, the elective count, the instructor email and the email draft.
4. Five questions asked through the real agent(s) with the LLM: an attendance rule, a slot, a count, an email, and an
   out-of-scope question that must be refused.

Steps 1 to 3 are deterministic. Step 4 depends on the LLM, so an occasional FAIL there is worth a look but isn't
necessarily a bug.

---

## 6. Evaluation

```bash
make eval multi_agent RUNS=3
make eval single_agent RUNS=3
make eval multi_agent RUNS=3 MODEL=qwen3:8b    # swap the LLM
make eval multi_agent RUNS=1 IDS=P01,S01,O01   # quick subset
make eval-all RUNS=3                           # both architectures
```

**Before evaluating, fill in `evaluation/questions.json` for your documents.** For each in-scope question:
- `expected_keywords`: words or numbers that must appear in a correct answer, e.g. `["75%"]` or `["D"]`.
  Use `"a|b"` for alternatives, e.g. `["75%|75 percent"]`. If you leave it empty, grade that question by hand.
- `expected_sources`: file name(s) the answer should cite, e.g. `["academic_regulations.pdf"]`.
- `expected_answer`: a human-readable reference answer (not used for scoring, but useful for the report).
- Feel free to edit or replace questions so that they match your documents (keep 20 to 30).

Each run writes `results/<model>_<mode>_<timestamp>/`:
- `summary.md`: the metrics table, per-category table, and **questions whose answers changed across runs**
- `results.csv`: one row per question per run, with an empty `manual_correct` column for hand grading
- `records.json`: full raw trace (answers, tool calls with arguments)

| Metric | How it is measured |
|---|---|
| Answer accuracy | all `expected_keywords` present in the answer (plus manual grading for the rest) |
| Correct refusals | out-of-scope question → `log_unanswered_question` called or "I don't know" reply |
| False refusals | in-scope question refused |
| Citation / groundedness | answer cites ≥1 KB file **and** every cited file was actually returned by a tool; *correct source* = cited file ∈ `expected_sources` |
| Correct tool / routing | `expected_tool` called / `expected_agent` received the question (multi only) |
| Stability | per question across runs: did the verdict change (refused ↔ answered, correct ↔ wrong) or did the text similarity drop below 0.8? |

The default temperature is 0.2, so some run-to-run variation is expected and worth discussing. Use `TEMPERATURE=0`
to compare against near-deterministic runs.

Copy the numbers into `report/report_template.md` to write the report.

---

## 7. Configuration

Defaults are in `config.py`. Change them in `.env`, or for a single run with an environment variable:

| Variable | Default | Meaning |
|---|---|---|
| `LLM_MODEL` | `llama3.1:8b` | Ollama model name |
| `OLLAMA_API_BASE` | `http://localhost:11434` | Ollama server |
| `TEMPERATURE` | `0.2` | LLM temperature |
| `NUM_CTX` | `8192` | context window passed to Ollama |
| `KB_DIR` | `data/knowledge_base` | knowledge base folder |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | `600` / `100` | characters (smaller = faster on CPU, see below) |
| `TOP_K` | `3` | chunks retrieved per search |
| `MAX_PASSAGE_CHARS` | `700` | max characters of one passage sent to the LLM |
| `MIN_SIMILARITY` | `0.50` | relevance cut-off (cosine) |

Example: `TOP_K=6 MIN_SIMILARITY=0.45 make chat multi_agent`.
`MIN_SIMILARITY` is the main knob for the refusal trade-off. Too high and the agent refuses valid questions; too low
and it gets weak chunks that invite guessing. Run `python main.py ask "..." --trace` on a few questions and check the
`similarity` values the tool returns to tune it for your documents.
`make smoke-test` also prints the similarity of a relevant query next to that of an off-topic query, which is a good
first indication of where the cut-off should be.

---

## 8. Troubleshooting

| Problem | Fix |
|---|---|
| Not sure what is wrong | `make doctor` |
| `Vector store not found` | run `make ingest` |
| `No virtual environment found` | run `make venv` |
| Connection refused to localhost:11434 | start Ollama (`ollama serve`) |
| Model prints a JSON tool call as text instead of calling it | make sure the model string uses `ollama_chat/` (done in `agents.py`); use a model with tool support (llama3.1, qwen3) |
| Answers ignore the retrieved text / instructions | context window too small: keep `NUM_CTX=8192`, or set `OLLAMA_CONTEXT_LENGTH=8192` before `ollama serve` |
| Lookup tools say "course not found" | check the CSV headers (section 4); then re-run so the tables are re-read |
| Slow on CPU | normal for an 8B model; the multi-agent mode makes at least 2 LLM calls per question |
| A PDF produced 0 chunks | it is scanned; OCR it or convert it to TXT |

---

## 9. Limitations / possible improvements
- Dense-only retrieval. A hybrid BM25 + dense search, or a cross-encoder re-ranker, would help with exact terms.
- Tables inside PDFs lose their structure when extracted.
- An 8B model sometimes routes wrongly or skips the citation. The eval script measures how often.
- `count_courses` infers the level from the first digit of the course number. This matches codes like `HSL4010`
  but would need changing for other numbering schemes.
