"""
End-to-end smoke test on the DUMMY data in data/sample/ (used by `make smoke-test`).

It uses its own index (chroma_db_sample/) and log file, so your real
knowledge-base index and unanswered-questions log are not touched.

  python scripts/smoke_test.py [--modes single,multi]
"""
import asyncio
import os
import re
import sys
import time
import warnings
import logging
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
# must be set before `config` is imported; these override .env on purpose
os.environ["KB_DIR"] = "data/sample"
os.environ["CHROMA_DIR"] = "chroma_db_sample"
os.environ["UNANSWERED_LOG"] = "logs/smoke_test_unanswered.csv"
os.environ.setdefault("LITELLM_LOG", "ERROR")
warnings.filterwarnings("ignore")
logging.basicConfig(level=logging.ERROR)

import config  # noqa: E402

results = []


def check(name, ok, detail=""):
    results.append(ok)
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  ({detail})" if detail else ""))


# ------------------------------------------------------------------ step 1-3: no LLM needed

def test_ingest():
    print("\n==> [1/4] Ingesting the sample knowledge base (data/sample -> chroma_db_sample/)")
    from helpdesk.ingest import ingest
    ingest()


def test_retrieval():
    print("\n==> [2/4] Testing retrieval (embedding search, no LLM)")
    from helpdesk import retriever
    hits = retriever.retrieve("attendance requirement to sit in the major exam")
    top = hits[0] if hits else {}
    check("attendance query -> sample_academic_rules.txt is the top hit",
          top.get("source") == "sample_academic_rules.txt", f"top={top.get('source')}, sim={top.get('similarity')}")
    check(f"top hit similarity >= MIN_SIMILARITY ({config.MIN_SIMILARITY})",
          top.get("similarity", 0) >= config.MIN_SIMILARITY, f"sim={top.get('similarity')}")
    off = retriever.retrieve("best biryani restaurant near the campus")
    print(f"        (for comparison, an off-topic query scores sim={off[0]['similarity'] if off else '-'})")


def test_tools():
    print("\n==> [3/4] Testing the tools directly (no LLM)")
    from helpdesk import tools
    r = tools.lookup_course("Autonomous Systems")
    check("lookup_course('Autonomous Systems') -> slot D", bool(r["matches"]) and r["matches"][0].get("slot") == "D")
    r = tools.count_courses("Humanities", "400", "elective")
    check("count_courses('Humanities', '400', 'elective') -> 2", r["count"] == 2, f"got {r['count']}: {r['courses']}")
    r = tools.count_courses("Humanities department", "400 level", "electives")
    check("count_courses('Humanities department', '400 level', 'electives') -> 2 (LLM-style wording)",
          r["count"] == 2, f"got {r['count']}")
    r = tools.lookup_instructor_email("CSL7570")
    check("lookup_instructor_email('CSL7570') -> dummy.sharma@example.edu", r.get("email") == "dummy.sharma@example.edu")
    r = tools.draft_email("CSL7570", "leave", "fever", "2 days")
    check("draft_email(...) is addressed correctly and mentions the course",
          r["to"] == "dummy.sharma@example.edu" and "CSL7570" in r["subject"])


# ------------------------------------------------------------------ step 4: full agent with the LLM

AGENT_CASES = [
    ("What is the attendance requirement to sit in the Major exam?", lambda a: "75" in a.text, "mentions 75%"),
    ("What is the slot for the course Autonomous Systems?", lambda a: re.search(r"\bD\b", a.text), "says slot D"),
    ("How many 400 level electives have been floated by the Humanities department in this semester?",
     lambda a: re.search(r"\b(2|two)\b", a.text, re.I), "says 2"),
    ("Write an email to the course instructor of CSL7570 that I need leave for 2 days",
     lambda a: "dummy.sharma@example.edu" in a.full_text and "Leave application" in a.full_text, "shows the draft"),
    ("What are the available dining options on the campus?",
     lambda a: "log_unanswered_question" in a.tools_used or "don't know" in a.text.lower(), "refuses + logs"),
]


async def test_agents(modes):
    print(f"\n==> [4/4] Asking the agent(s) with the LLM ({config.LLM_MODEL}); this is the slow part")
    from helpdesk.session import Helpdesk
    for mode in modes:
        print(f"\n  --- {mode}-agent ---")
        desk = Helpdesk(mode)
        for q, ok_fn, expect in AGENT_CASES:
            t0 = time.time()
            try:
                ans = await desk.ask(q, fresh_session=True)
            except Exception as e:
                check(f"[{mode}] {q[:60]}", False, f"error: {e}")
                continue
            check(f"[{mode}] {q[:60]}", bool(ok_fn(ans)),
                  f"{expect}; {time.time() - t0:.0f}s; agent={ans.agent}; tools={ans.tools_used}")
            print("        answer: " + ans.full_text.replace("\n", " ")[:160])


def main():
    modes = ["single", "multi"]
    if "--modes" in sys.argv:
        modes = sys.argv[sys.argv.index("--modes") + 1].split(",")

    test_ingest()
    test_retrieval()
    test_tools()
    asyncio.run(test_agents(modes))

    passed = sum(results)
    print(f"\n==> Smoke test finished: {passed}/{len(results)} checks passed")
    print("    LLM answers can vary between runs; a single agent FAIL is worth a look, not necessarily a bug.")
    print(f"    Refused questions from this test were logged to {config.UNANSWERED_LOG.relative_to(config.ROOT)}")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
