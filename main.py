"""
Academic Helpdesk - command line entry point.

  python main.py ingest                         # build the vector store from data/knowledge_base
  python main.py chat  [--mode multi|single]    # interactive chat
  python main.py ask "What is the slot of CSL7570?" [--mode ...] [--trace]
"""
import argparse
import asyncio
import json
import logging
import os
import re
import warnings

# keep the terminal readable (LiteLLM / ADK are chatty)
warnings.filterwarnings("ignore")
logging.basicConfig(level=logging.ERROR)
os.environ.setdefault("LITELLM_LOG", "ERROR")

import config  # noqa: E402


TRACE_RE = re.compile(r"\btrace\s*(?:=\s*)?(on|off|1|0)\s*$", re.I)


def _print_search_results(response):
    """Pretty-print the chunks returned by a search_documents call."""
    results = response.get("results", [])
    note = response.get("note", "")
    if note:
        print(f"      [!] {note}")
        return
    print(f"      Retrieved {len(results)} chunk(s):")
    for i, r in enumerate(results, 1):
        # Show first 200 chars of the chunk text as a preview
        preview = r.get("text", "")
        if len(preview) > 200:
            preview = preview[:200].rstrip() + "..."
        print(f"      Chunk {i}:")
        print(f"        Source     : {r.get('cite_as') or r.get('source', '?')}")
        print(f"        Similarity : {r.get('similarity', '?')}")
        print(f"        Preview    : {preview}")


def _print_source_files(ans):
    """Print the source files used when search_documents was NOT called."""
    sources = set()
    for r in ans.tool_results:
        resp = r.get("response", {})
        if isinstance(resp, dict):
            src = resp.get("source") or resp.get("source_file")
            if isinstance(src, list):
                sources.update(src)
            elif src:
                sources.add(src)
    if sources:
        print(f"   [sources] {', '.join(sorted(sources))}")


def print_answer(ans, trace):
    print(f"\n[{ans.agent}] {ans.full_text}\n")

    # Build a lookup: tool_name -> list of responses (same order as calls)
    # tool_results already stores {"name": ..., "response": ...} so match by name
    search_results = [r["response"] for r in ans.tool_results
                      if r["name"] == "search_documents"]

    if trace:
        # Show every tool call; for search_documents, also show retrieved chunks inline
        search_idx = 0
        for c in ans.tool_calls:
            print(f"   -> tool: {c['name']}({json.dumps(c['args'])})")
            if c["name"] == "search_documents" and search_idx < len(search_results):
                _print_search_results(search_results[search_idx])
                search_idx += 1
        print()
    else:
        # No trace: if search_documents was used, show retrieved chunks after the answer
        # otherwise, just tell the user which source files were used
        if search_results:
            print("   [retrieved chunks]")
            for resp in search_results:
                _print_search_results(resp)
            print()
        else:
            _print_source_files(ans)
            print()


async def chat(mode, model, trace):
    from helpdesk.session import Helpdesk
    desk = Helpdesk(mode, model)
    print(f"Academic Helpdesk ({mode}-agent, model={desk.model_name}). Type 'exit' to quit, "
          f"'new' for a fresh session, 'trace on' / 'trace off' to show tool calls.\n")
    while True:
        try:
            q = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if q.lower() in {"exit", "quit"}:
            break
        if q.lower() == "new":
            await desk.new_session()
            print("(new session)\n")
            continue
        # "trace on" / "trace off", also "TRACE=1" / "TRACE=0" (the make option), alone or after a question
        m = TRACE_RE.search(q)
        if m:
            trace = m.group(1).lower() in {"on", "1"}
            q = q[:m.start()].strip()
            print(f"(tool trace {'on' if trace else 'off'})\n")
        if q:
            print_answer(await desk.ask(q), trace)


async def ask_once(question, mode, model, trace):
    from helpdesk.session import Helpdesk
    print_answer(await Helpdesk(mode, model).ask(question), trace)


def main():
    p = argparse.ArgumentParser(description="Academic Helpdesk Agent")
    sub = p.add_subparsers(dest="cmd", required=True)

    # the KB folder is set with the KB_DIR env var (not a flag) so that ingest and the
    # CSV lookup tools always read the same folder
    sub.add_parser("ingest", help=f"index {config.KB_DIR} into ChromaDB")

    for name in ["chat", "ask"]:
        s = sub.add_parser(name)
        if name == "ask":
            s.add_argument("question")
        s.add_argument("--mode", choices=["single", "multi"], default="multi")
        s.add_argument("--model", default=None, help=f"Ollama model (default {config.LLM_MODEL})")
        s.add_argument("--trace", action="store_true", help="show the tool calls")

    args = p.parse_args()
    if args.cmd == "ingest":
        from helpdesk.ingest import ingest
        ingest()
    elif args.cmd == "chat":
        asyncio.run(chat(args.mode, args.model, args.trace))
    else:
        asyncio.run(ask_once(args.question, args.mode, args.model, args.trace))


if __name__ == "__main__":
    main()
