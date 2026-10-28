"""
Central configuration for the Academic Helpdesk.

Every value can be set in the .env file or overridden with an environment
variable of the same name, e.g.  LLM_MODEL=qwen3:8b python main.py chat
(real environment variables win over .env).
"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env", override=False)
except ImportError:  # python-dotenv not installed yet -> just use the environment / defaults
    pass


def _path(name, default):
    """Read a path setting; relative paths are taken relative to the project folder."""
    p = Path(os.getenv(name, default))
    return p if p.is_absolute() else ROOT / p


# ---------------- Paths ----------------
KB_DIR = _path("KB_DIR", "data/knowledge_base")
CHROMA_DIR = _path("CHROMA_DIR", "chroma_db")
UNANSWERED_LOG = _path("UNANSWERED_LOG", "logs/unanswered_questions.csv")
LOG_DIR = UNANSWERED_LOG.parent
RESULTS_DIR = ROOT / "results"

SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".csv"}

# Department of a course CSV that has no "Department" column, by file name (without .csv).
# Files not listed here get their file name as department ("physics.csv" -> "Physics").
DEPARTMENT_BY_FILE = {
    "cse": "Computer Science and Engineering",
    "electrical": "Electrical Engineering",
    "mechanical": "Mechanical Engineering",
    "civil": "Civil and Infrastructure Engineering",
}
# Other names students use for a department (initials such as "CSE", "EE", "ME" work automatically)
DEPARTMENT_ALIASES = {
    "Computer Science and Engineering": ["cs", "computer science", "computer"],
    "Electrical Engineering": ["eee", "electrical"],
    "Mechanical Engineering": ["mech", "mechanical"],
    "Civil and Infrastructure Engineering": ["ce", "civil"],
    "Humanities": ["hss", "liberal arts", "lal", "liberal", "humanities social sciences"],
}

# ---------------- Embeddings / Vector store ----------------
EMBED_MODEL = os.getenv("EMBED_MODEL", "BAAI/bge-small-en-v1.5")
# bge models are trained with this instruction prepended to *queries only* (not to passages)
BGE_QUERY_INSTRUCTION = "Represent this sentence for searching relevant passages: "
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "academic_kb")

# ---------------- Chunking ----------------
# On a CPU the LLM reads ~20 tokens/s, so every retrieved character costs time:
# 600-char chunks x top-3 is about half the text of 900 x top-4.
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", 600))        # characters per chunk (~130 tokens)
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", 100))  # characters carried over to the next chunk
CSV_ROWS_PER_CHUNK = int(os.getenv("CSV_ROWS_PER_CHUNK", 8))

# ---------------- Retrieval ----------------
TOP_K = int(os.getenv("TOP_K", 3))
# safety cap on the text of one passage sent to the LLM (CSV blocks can be long);
# kept above CHUNK_SIZE so normal text chunks are never cut
MAX_PASSAGE_CHARS = int(os.getenv("MAX_PASSAGE_CHARS", 700))
# cosine similarity below this => treat as "nothing relevant found".
# bge-small typically gives 0.6-0.85 for relevant passages; tune this on your own KB.
MIN_SIMILARITY = float(os.getenv("MIN_SIMILARITY", 0.50))

# ---------------- LLM (Ollama via LiteLLM) ----------------
LLM_MODEL = os.getenv("LLM_MODEL", "llama3.1:8b")
OLLAMA_API_BASE = os.getenv("OLLAMA_API_BASE", "http://localhost:11434")
os.environ.setdefault("OLLAMA_API_BASE", OLLAMA_API_BASE)  # LiteLLM reads this
TEMPERATURE = float(os.getenv("TEMPERATURE", 0.2))
# Ollama's default context window is small; tool outputs + instructions need more.
NUM_CTX = int(os.getenv("NUM_CTX", 8192))
# upper limit on the length of one LLM reply (answers are short; email drafts are printed by the program)
MAX_OUTPUT_TOKENS = int(os.getenv("MAX_OUTPUT_TOKENS", 400))

APP_NAME = "academic_helpdesk"
REFUSAL_TEXT = "I don't know the answer to this based on the available academic documents."
