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
import warnings

# keep the terminal readable (LiteLLM / ADK are chatty)
warnings.filterwarnings("ignore")
logging.basicConfig(level=logging.ERROR)
os.environ.setdefault("LITELLM_LOG", "ERROR")

import config  # noqa: E402


def print_answer(ans, trace):
    print(f"\n[{ans.agent}] {ans.full_text}\n")
    if trace:
        for c in ans.tool_calls:
            print(f"   -> tool: {c['name']}({json.dumps(c['args'])})")
        print()


async def chat(mode, model, trace):
    from helpdesk.session import Helpdesk
    desk = Helpdesk(mode, model)
    print(f"Academic Helpdesk ({mode}-agent, model={desk.model_name}). "
          f"Type 'exit' to quit, 'new' for a fresh session.\n")
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
