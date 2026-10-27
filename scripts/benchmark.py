"""
Latency benchmark: time a few questions and count the tokens the LLM had to read.

  python scripts/benchmark.py --label before --modes single,multi
  python scripts/benchmark.py --label after  --modes single,multi

On a CPU, reading the prompt dominates the time, so prompt tokens explain most of
the latency. Every run is appended to results/benchmark.csv for the report.
"""
import argparse
import asyncio
import csv
import json
import logging
import os
import sys
import time
import urllib.request
import warnings
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
warnings.filterwarnings("ignore")
logging.basicConfig(level=logging.ERROR)
os.environ.setdefault("LITELLM_LOG", "ERROR")

import config  # noqa: E402
from helpdesk.session import Helpdesk  # noqa: E402

DEFAULT_QUESTIONS = ["What is the attendance requirement to sit in the Major exam?"]


def warm_up():
    """Load the model into RAM first, so the model load time is not counted.
    An unrelated prompt also clears Ollama's prompt cache, so every run starts equal."""
    body = json.dumps({"model": config.LLM_MODEL, "prompt": "Hello", "stream": False,
                       "options": {"num_ctx": config.NUM_CTX, "num_predict": 1}}).encode()
    req = urllib.request.Request(f"{config.OLLAMA_API_BASE}/api/generate", body,
                                 {"Content-Type": "application/json"})
    urllib.request.urlopen(req, timeout=600).read()


async def run(args):
    questions = args.questions or DEFAULT_QUESTIONS
    out = config.RESULTS_DIR / "benchmark.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    new_file = not out.exists()
    print(f"==> Benchmark '{args.label}' | model={config.LLM_MODEL} TOP_K={config.TOP_K} "
          f"CHUNK_SIZE={config.CHUNK_SIZE}")

    with open(out, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(["timestamp", "label", "mode", "model", "top_k", "question", "seconds",
                        "llm_calls", "prompt_tokens", "output_tokens", "tools", "answer"])
        for mode in args.modes.split(","):
            desk = Helpdesk(mode)
            for q in questions:
                warm_up()
                t0 = time.time()
                ans = await desk.ask(q, fresh_session=True)
                secs = time.time() - t0
                print(f"  [{mode:<6}] {secs:6.1f}s | {ans.llm_calls} LLM calls | "
                      f"{ans.prompt_tokens} prompt tokens | {ans.output_tokens} output tokens | tools={ans.tools_used}")
                print(f"           answer: {ans.text.replace(chr(10), ' ')[:150]}")
                w.writerow([datetime.now().isoformat(timespec="seconds"), args.label, mode, config.LLM_MODEL,
                            config.TOP_K, q, round(secs, 1), ans.llm_calls, ans.prompt_tokens,
                            ans.output_tokens, ";".join(ans.tools_used), ans.text])
                f.flush()
    print(f"==> Appended to {out.relative_to(config.ROOT)}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--label", default="run")
    p.add_argument("--modes", default="single,multi")
    p.add_argument("--questions", nargs="*", default=None)
    asyncio.run(run(p.parse_args()))


if __name__ == "__main__":
    main()
