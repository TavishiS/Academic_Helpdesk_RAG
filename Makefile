# Academic Helpdesk: run `make` (or `make help`) to see every command.
#
#   make venv                  create .venv and install missing requirements
#   make ingest                index data/knowledge_base into ChromaDB
#   make chat single_agent     chat with the single-agent helpdesk
#   make chat multi_agent      chat with the multi-agent helpdesk
#   make smoke-test            end-to-end test on the dummy sample data

SHELL   := /bin/bash
VENV    := .venv
PY      := $(VENV)/bin/python

# optional variables:  make eval multi_agent RUNS=5 MODEL=qwen3:8b TRACE=1
RUNS    ?= 3
MODEL   ?=
TRACE   ?=
TORCH   ?=
IDS     ?=
LABEL   ?=
Q       ?=

MODEL_FLAG := $(if $(MODEL),--model $(MODEL),)
TRACE_FLAG := $(if $(TRACE),--trace,)

# "make chat single_agent": the second word picks the architecture (multi by default)
AGENT := $(word 2,$(MAKECMDGOALS))
MODE  := $(if $(filter single_agent,$(AGENT)),single,multi)

# settings as Python sees them (.env + environment), for the messages we print
CFG = $(shell $(PY) -c "import config; print(config.$(1))" 2>/dev/null)

.DEFAULT_GOAL := help
.PHONY: help venv torch-cpu env doctor pull-model ocr ingest faculty-contacts chat ask smoke-test eval eval-all benchmark unanswered clean single_agent multi_agent

# every command, variant and option; keep this in sync when adding a target
define HELP_TEXT
Academic Helpdesk: all make commands
(single_agent / multi_agent picks the architecture; when it is left out, multi_agent is used)

SETUP
  make venv                              create .venv (if missing), install ONLY missing/outdated requirements, create .env
  make venv TORCH=cpu                    same, but install the small CPU-only PyTorch if torch is not installed yet
  make torch-cpu                         install the CPU-only PyTorch, or replace a GPU (CUDA) build with it (frees GBs)
  make env                               create .env from .env.example (never overwrites an existing .env)
  make doctor                            check Ollama, the LLM model, knowledge base files and index; show settings
  make pull-model                        download the LLM named in .env with Ollama
  make pull-model MODEL=qwen3:8b         download another LLM (needed before using MODEL=... below)

KNOWLEDGE BASE
  make ocr                               add a text layer to scanned (image-only) PDFs in KB_DIR (needs tesseract-ocr)
  make ingest                            (re)build the vector index from KB_DIR: load -> chunk -> embed -> ChromaDB
  make faculty-contacts                  rebuild faculty_contacts.csv from the instructors in the course CSVs (fake emails/phones), then run make ingest

USE THE HELPDESK
  make chat single_agent                 interactive chat with the single agent ('new' = fresh session, 'exit' = quit)
  make chat multi_agent                  interactive chat with orchestrator + policy/schedule/email agents
  make chat multi_agent TRACE=1          ... and print every tool call (or type 'trace on' in the chat)
  make chat single_agent MODEL=qwen3:8b  ... with another LLM
  make ask Q="your question"             ask one question (multi_agent), tool calls are shown
  make ask Q="your question" single_agent
  make unanswered                        show the questions that were logged for a human to answer

TESTING AND EVALUATION
  make smoke-test                        end-to-end test on the DUMMY data/sample, both architectures
  make smoke-test single_agent           ... only one architecture (faster); same for multi_agent
  make eval single_agent                 evaluate on evaluation/questions.json (default RUNS=3)
  make eval multi_agent RUNS=5           ... with a different number of runs per question
  make eval multi_agent MODEL=qwen3:8b   ... with another LLM (model comparison)
  make eval multi_agent IDS=P01,S01,O01  ... only some questions (quick check)
  make eval-all                          evaluate single_agent, then multi_agent (accepts RUNS= and MODEL=)
  make benchmark                         time one question on both architectures + count LLM tokens
  make benchmark single_agent LABEL=x    ... one architecture, rows labelled 'x' in results/benchmark.csv

HOUSEKEEPING
  make clean                             delete vector indexes and caches (documents, logs and results are kept)
  make help  (or just: make)             show this list

OPTIONS (add to any command above)
  MODEL=<ollama model>                   LLM to use for this run (chat, ask, eval, eval-all, pull-model)
  TRACE=1                                show the tool calls (chat)
  RUNS=<n>                               runs per question (eval, eval-all; default 3)
  IDS=a,b,c                              only these question IDs (eval)
  LABEL=<text>                           label of the rows written by benchmark
  TORCH=cpu                              CPU-only PyTorch (venv)
  <any .env setting>=<value>             override it for one run, e.g. TOP_K=5 make chat multi_agent
endef
export HELP_TEXT

help: ## show every command
	@w=$$(tput cols 2>/dev/null || echo $${COLUMNS:-100}); [ "$$w" -lt 60 ] && w=60; \
	{ \
		echo "$$HELP_TEXT"; \
		if [ -x $(PY) ]; then \
			echo; \
			echo "CURRENT SETTINGS (.env)"; \
			echo "  KB_DIR=$(call CFG,KB_DIR)"; \
			echo "  LLM_MODEL=$(call CFG,LLM_MODEL)  TOP_K=$(call CFG,TOP_K)  CHUNK_SIZE=$(call CFG,CHUNK_SIZE)  MIN_SIMILARITY=$(call CFG,MIN_SIMILARITY)"; \
		else \
			echo; echo "No virtual environment yet: start with 'make venv'."; \
		fi; \
	} | awk -v width=$$w -f scripts/format_help.awk

# ------------------------------------------------------------------ setup

venv: ## create .venv and install only the missing requirements
	@if [ -x $(PY) ]; then \
		echo "==> Using existing virtual environment $(VENV)/"; \
	else \
		echo "==> Creating virtual environment in $(VENV)/"; \
		python3 -m venv $(VENV) || exit 1; \
	fi
	@echo "==> Checking requirements.txt against what is installed in $(VENV)/"
	@$(PY) scripts/install_requirements.py $(if $(filter cpu,$(TORCH)),--torch-cpu,)
	@$(MAKE) --no-print-directory env
	@echo
	@echo "==> Setup complete. Next: 'make doctor' to check Ollama, then 'make smoke-test'."

torch-cpu: _need-venv ## install the CPU-only PyTorch (or replace a CUDA build with it)
	@v=$$($(PY) -c "import torch; print(torch.__version__)" 2>/dev/null); \
	if [[ "$$v" == *+cpu ]]; then \
		echo "==> PyTorch $$v is already the CPU-only build, nothing to do."; exit 0; \
	fi; \
	if [ -n "$$v" ]; then \
		echo "==> Found PyTorch $$v (GPU/CUDA build): replacing it with the CPU-only build"; \
		flags="--force-reinstall --no-deps"; \
	else \
		echo "==> PyTorch is not installed: installing the CPU-only build"; flags=""; \
	fi; \
	echo "    (sentence-transformers runs the embedding model on PyTorch; Ollama does not use it)"; \
	$(PY) -m pip install $$flags torch --index-url https://download.pytorch.org/whl/cpu || exit 1; \
	gpu=$$($(PY) -m pip list 2>/dev/null | awk '/^(nvidia-|triton)/ {print $$1}'); \
	if [ -n "$$gpu" ]; then \
		echo "==> Removing CUDA-only packages the CPU build does not need: $$gpu"; \
		$(PY) -m pip uninstall -y $$gpu; \
	fi; \
	echo "==> Done: $$($(PY) -c 'import torch; print("PyTorch", torch.__version__)')"

env: ## create .env from .env.example (if it does not exist)
	@if [ -f .env ]; then \
		echo "==> .env already exists (not overwritten)"; \
	else \
		cp .env.example .env; \
		echo "==> Created .env from .env.example: edit it to change KB_DIR, LLM_MODEL, ..."; \
	fi

_need-venv:
	@if [ ! -x $(PY) ]; then echo "✘ No virtual environment found. Run 'make venv' first."; exit 1; fi

doctor: _need-venv ## check Ollama, the LLM model, the knowledge base and the index
	@$(PY) scripts/preflight.py || true
	@echo
	@echo "    Settings in use: KB_DIR=$(call CFG,KB_DIR)"
	@echo "                     LLM_MODEL=$(call CFG,LLM_MODEL)  TEMPERATURE=$(call CFG,TEMPERATURE)  TOP_K=$(call CFG,TOP_K)  MIN_SIMILARITY=$(call CFG,MIN_SIMILARITY)"

pull-model: _need-venv ## download the LLM from .env (or MODEL=...) with Ollama
	@m="$(if $(MODEL),$(MODEL),$(call CFG,LLM_MODEL))"; \
	echo "==> Pulling $$m with Ollama (about 5 GB for an 8B model)"; \
	ollama pull $$m

# ------------------------------------------------------------------ RAG index

ocr: _need-venv ## add a text layer to all scanned (image-only) PDFs in KB_DIR using ocrmypdf
	@echo "==> Running OCR on scanned PDFs in $(call CFG,KB_DIR)"
	@echo "    NOTE: requires 'tesseract-ocr' system package:"
	@echo "      sudo apt install tesseract-ocr   (Debian/Ubuntu)"
	@echo "      brew install tesseract           (macOS)"
	@failed=0; \
	for pdf in $(call CFG,KB_DIR)/*.pdf; do \
		[ -f "$$pdf" ] || continue; \
		chars=$$($(PY) -c "from pypdf import PdfReader; r=PdfReader('$$pdf'); print(sum(len(p.extract_text() or '') for p in r.pages))" 2>/dev/null); \
		if [ "$$chars" -eq 0 ] 2>/dev/null; then \
			echo "    OCR: $$pdf (0 chars extracted → scanned PDF)"; \
			$(PY) -m ocrmypdf --skip-text "$$pdf" "$$pdf" && echo "       ✓ done" || { echo "       ✘ failed"; failed=1; }; \
		else \
			echo "    skip: $$pdf ($$chars chars already extractable)"; \
		fi; \
	done; \
	if [ "$$failed" -eq 1 ]; then \
		echo "==> Some files failed. Is tesseract installed? (sudo apt install tesseract-ocr)"; exit 1; \
	fi
	@echo "==> OCR done. Run 'make ingest' to rebuild the vector index."

ingest: _need-venv ## (re)build the vector index from KB_DIR (.env)
	@echo "==> Building the vector index"
	@echo "    knowledge base : $(call CFG,KB_DIR)"
	@echo "    index folder   : $(call CFG,CHROMA_DIR)"
	@echo "    embedding model: $(call CFG,EMBED_MODEL) (downloaded from HuggingFace on first use)"
	@echo "    steps          : load pdf/txt/csv -> chunk ($(call CFG,CHUNK_SIZE) chars, $(call CFG,CHUNK_OVERLAP) overlap) -> embed -> store"
	@$(PY) main.py ingest

faculty-contacts: _need-venv ## rebuild faculty_contacts.csv from the course CSVs
	@echo "==> Rebuilding faculty_contacts.csv from the instructors in the course CSVs of $(call CFG,KB_DIR)"
	@echo "    emails (@iitj.example) and phone numbers (starting 2-5) are FAKE; same name -> same details"
	@$(PY) scripts/build_faculty_contacts.py
	@echo "    run 'make ingest' so that the search index also has the new contacts"

# ------------------------------------------------------------------ using the agent

chat: _need-venv ## chat: make chat single_agent | make chat multi_agent
	@$(PY) scripts/preflight.py >/dev/null || { $(PY) scripts/preflight.py; echo; echo "✘ Fix the issues above first."; exit 1; }
	@echo "==> Starting the $(MODE)-agent helpdesk (model: $(if $(MODEL),$(MODEL),$(call CFG,LLM_MODEL)))"
	@echo "    $(if $(filter single,$(MODE)),one agent with all tools,orchestrator -> policy_agent / schedule_agent / email_agent)"
	@echo "    type 'new' for a fresh session, 'trace on' / 'trace off' to show tool calls, 'exit' to quit"
	@$(PY) main.py chat --mode $(MODE) $(MODEL_FLAG) $(TRACE_FLAG)

ask: _need-venv ## ask one question: make ask Q="..." [single_agent|multi_agent]
	@if [ -z "$(Q)" ]; then echo 'Usage: make ask Q="your question" [single_agent|multi_agent]'; exit 1; fi
	@$(PY) scripts/preflight.py >/dev/null || { $(PY) scripts/preflight.py; exit 1; }
	@echo "==> Asking the $(MODE)-agent helpdesk"
	@$(PY) main.py ask "$(Q)" --mode $(MODE) $(MODEL_FLAG) --trace

unanswered: ## show questions the agent could not answer (for human follow-up)
	@f="$(call CFG,UNANSWERED_LOG)"; \
	if [ -f "$$f" ]; then echo "==> $$f"; column -s, -t < "$$f" 2>/dev/null || cat "$$f"; \
	else echo "==> No unanswered questions logged yet ($$f)"; fi

# ------------------------------------------------------------------ testing / evaluation

smoke-test: _need-venv ## end-to-end test on the DUMMY data in data/sample (does not touch your real index)
	@echo "==> Smoke test: ingest -> retrieval -> tools -> agents, using data/sample/"
	@$(PY) scripts/preflight.py --no-index >/dev/null || { $(PY) scripts/preflight.py --no-index; exit 1; }
	@$(PY) scripts/smoke_test.py $(if $(AGENT),--modes $(MODE),)

eval: _need-venv ## run the evaluation: make eval single_agent | multi_agent [RUNS=3 MODEL=.. IDS=P01,O01]
	@$(PY) scripts/preflight.py >/dev/null || { $(PY) scripts/preflight.py; exit 1; }
	@echo "==> Evaluating the $(MODE)-agent system on evaluation/questions.json, $(RUNS) run(s)"
	@echo "    each question is asked in a fresh session; results go to results/<model>_$(MODE)_<time>/"
	@$(PY) evaluation/run_eval.py --mode $(MODE) --runs $(RUNS) $(MODEL_FLAG) $(if $(IDS),--ids $(IDS),)

eval-all: _need-venv ## evaluate both architectures, one after the other
	@$(MAKE) --no-print-directory eval single_agent RUNS=$(RUNS) MODEL=$(MODEL)
	@$(MAKE) --no-print-directory eval multi_agent RUNS=$(RUNS) MODEL=$(MODEL)

benchmark: _need-venv ## time one question and count LLM tokens: make benchmark [LABEL=after]
	@$(PY) scripts/preflight.py >/dev/null || { $(PY) scripts/preflight.py; exit 1; }
	@echo "==> Timing the same question on $(if $(AGENT),the $(MODE)-agent system,both architectures) (model is warmed up first)"
	@echo "    reading the prompt is the slow part on a CPU, so prompt tokens are reported too"
	@$(PY) scripts/benchmark.py --label $(if $(LABEL),$(LABEL),run) --modes $(if $(AGENT),$(MODE),single,multi)

# ------------------------------------------------------------------ housekeeping

clean: ## delete the vector indexes and Python caches (documents, logs and results are kept)
	@echo "==> Removing chroma_db/, chroma_db_sample/ and __pycache__ folders"
	@rm -rf chroma_db chroma_db_sample
	@find . -name __pycache__ -not -path "./$(VENV)/*" -prune -exec rm -rf {} +
	@echo "    run 'make ingest' to rebuild the index"

# words used as arguments ("make chat single_agent"): do nothing on their own
single_agent multi_agent:
	@:
