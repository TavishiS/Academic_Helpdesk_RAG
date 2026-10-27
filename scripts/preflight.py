"""
Checks that everything needed to run the agent is in place (used by `make doctor`
and before `make chat` / `make ask` / `make eval`).

  python scripts/preflight.py [--no-index]
"""
import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402


def check_ollama():
    try:
        with urllib.request.urlopen(f"{config.OLLAMA_API_BASE}/api/tags", timeout=3) as r:
            models = [m["name"] for m in json.load(r).get("models", [])]
    except Exception:
        print(f"  ✘ Ollama server not reachable at {config.OLLAMA_API_BASE}")
        print("      -> start it with:  ollama serve")
        return False
    print(f"  ✔ Ollama server running at {config.OLLAMA_API_BASE}")

    wanted = config.LLM_MODEL if ":" in config.LLM_MODEL else config.LLM_MODEL + ":latest"
    if wanted not in models:
        print(f"  ✘ Model '{config.LLM_MODEL}' is not pulled (available: {', '.join(models) or 'none'})")
        print(f"      -> run:  make pull-model   (or: ollama pull {config.LLM_MODEL})")
        return False
    print(f"  ✔ Model '{config.LLM_MODEL}' available")
    return True


def check_index():
    try:
        import chromadb
        n = chromadb.PersistentClient(path=str(config.CHROMA_DIR)).get_collection(config.COLLECTION_NAME).count()
    except Exception:
        print(f"  ✘ No vector index found in {config.CHROMA_DIR}")
        print("      -> run:  make ingest")
        return False
    print(f"  ✔ Vector index: {n} chunks in {config.CHROMA_DIR.name}/")
    return n > 0


def main():
    print("==> Pre-flight checks")
    files = [p for p in config.KB_DIR.rglob("*") if p.suffix.lower() in config.SUPPORTED_EXTENSIONS]
    print(f"  {'✔' if files else '!'} Knowledge base: {len(files)} file(s) in {config.KB_DIR}")
    ok = check_ollama()
    if "--no-index" not in sys.argv:
        ok = check_index() and ok
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
