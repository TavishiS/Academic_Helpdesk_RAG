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
.PHONY: help venv env doctor pull-model ingest chat ask smoke-test eval eval-all benchmark unanswered clean single_agent multi_agent

help: ## show this help
	@echo "Academic Helpdesk: available commands"
	@echo
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  make %-26s %s\n", $$1, $$2}'
	@echo
	@echo "Examples:"
	@echo "  make venv                         (first time; add TORCH=cpu on a laptop without NVIDIA GPU)"
	@echo "  make venv TORCH=cpu               (add TORCH=cpu on a laptop without NVIDIA GPU)"
	@echo "  make smoke-test"
	@echo "  make ingest"
	@echo "  make chat single_agent"
	@echo "  make chat multi_agent TRACE=1     (also show the tool calls)"
	@echo "  make ask Q=\"What is the slot for Autonomous Systems?\""
	@echo "  make eval single_agent RUNS=3"
	@echo "  make eval multi_agent MODEL=qwen3:8b"

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

ingest: _need-venv ## (re)build the vector index from KB_DIR (.env)
	@echo "==> Building the vector index"
	@echo "    knowledge base : $(call CFG,KB_DIR)"
	@echo "    index folder   : $(call CFG,CHROMA_DIR)"
	@echo "    embedding model: $(call CFG,EMBED_MODEL) (downloaded from HuggingFace on first use)"
	@echo "    steps          : load pdf/txt/csv -> chunk ($(call CFG,CHUNK_SIZE) chars, $(call CFG,CHUNK_OVERLAP) overlap) -> embed -> store"
	@$(PY) main.py ingest

# ------------------------------------------------------------------ using the agent

chat: _need-venv ## chat: make chat single_agent | make chat multi_agent
	@$(PY) scripts/preflight.py >/dev/null || { $(PY) scripts/preflight.py; echo; echo "✘ Fix the issues above first."; exit 1; }
	@echo "==> Starting the $(MODE)-agent helpdesk (model: $(if $(MODEL),$(MODEL),$(call CFG,LLM_MODEL)))"
	@echo "    $(if $(filter single,$(MODE)),one agent with all tools,orchestrator -> policy_agent / schedule_agent / email_agent)"
	@echo "    type 'new' for a fresh session, 'exit' to quit$(if $(TRACE),, | add TRACE=1 to see tool calls)"
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
