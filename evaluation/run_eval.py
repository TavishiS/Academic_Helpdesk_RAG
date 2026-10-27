"""
Evaluation of the helpdesk on the question set.

  python evaluation/run_eval.py --mode multi  --runs 3
  python evaluation/run_eval.py --mode single --runs 3
  python evaluation/run_eval.py --mode multi  --runs 3 --model qwen3:8b

Metrics
  accuracy      : all expected_keywords appear in the answer (questions without keywords
                  are left for manual grading -> 'manual_correct' column in the CSV)
  groundedness  : answer cites >=1 KB file, every cited file was really returned by a tool,
                  and (if expected_sources is filled) one of the expected files is cited
  refusals      : out-of-scope questions refused (correct refusal) / in-scope refused (false refusal)
  tool / route  : the expected tool was called / the expected specialist agent was used
  stability     : questions whose verdict or wording changed across the runs
Each question is asked in a fresh session so answers don't leak into each other.
"""
import argparse
import asyncio
import csv
import json
import logging
import os
import re
import sys
import time
import warnings
from datetime import datetime
from difflib import SequenceMatcher
from itertools import combinations
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
warnings.filterwarnings("ignore")
logging.basicConfig(level=logging.ERROR)
os.environ.setdefault("LITELLM_LOG", "ERROR")

import config  # noqa: E402
from helpdesk.session import Helpdesk  # noqa: E402

REFUSAL_PATTERN = re.compile(r"don't know|do not know|could not find|couldn't find|not able to find|"
                             r"cannot answer|can't answer|no information|not available in", re.I)


# ------------------------------------------------------------------ scoring helpers

def collect_sources(obj, out=None):
    """Walk a tool response and collect every value stored under a 'source' key."""
    out = set() if out is None else out
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "source":
                out.update(v if isinstance(v, list) else [v])
            else:
                collect_sources(v, out)
    elif isinstance(obj, list):
        for v in obj:
            collect_sources(v, out)
    return {str(s) for s in out if s}


def cited_files(answer, kb_files):
    """KB files mentioned in the answer (by full name or by name without extension)."""
    text = answer.lower()
    return sorted(f for f in kb_files if f.lower() in text or Path(f).stem.lower() in text)


def keyword_hit(answer, keywords):
    """Every keyword must appear (case-insensitive). "a|b" means either a or b is fine.
    "re:<regex>" is a regular expression, for short answers where a substring would match
    anything, e.g. "re:\\bE\\b" for slot E or "re:\\b5\\b" for a count of 5."""
    def hit(kw):
        if kw.startswith("re:"):
            return re.search(kw[3:], answer, re.I) is not None
        return any(alt.strip().lower() in answer.lower() for alt in kw.split("|"))
    return all(hit(kw) for kw in keywords)


def score(q, ans, kb_files):
    refused = "log_unanswered_question" in ans.tools_used or bool(REFUSAL_PATTERN.search(ans.text))
    retrieved = set()
    for r in ans.tool_results:
        retrieved |= collect_sources(r["response"])
    cited = cited_files(ans.text, kb_files)

    agents = {c["args"].get("agent_name") for c in ans.tool_calls if c["name"] == "transfer_to_agent"}
    agents.add(ans.agent)

    row = {
        "refused": refused,
        "correct_refusal": refused if q["should_refuse"] else None,
        "false_refusal": refused if not q["should_refuse"] else None,
        "auto_correct": None, "has_citation": None, "citation_valid": None, "citation_correct": None,
        "tool_ok": q.get("expected_tool") in ans.tools_used if q.get("expected_tool") else None,
        "route_ok": q.get("expected_agent") in agents if q.get("expected_agent") else None,
        "cited": cited, "retrieved_sources": sorted(retrieved),
    }
    if not q["should_refuse"] and not refused:
        if q.get("expected_keywords"):
            row["auto_correct"] = keyword_hit(ans.full_text, q["expected_keywords"])
        if q["category"] != "email":  # email drafts are judged by tool use, not citations
            row["has_citation"] = bool(cited)
            row["citation_valid"] = bool(cited) and set(cited) <= retrieved
            if q.get("expected_sources"):
                row["citation_correct"] = bool(set(cited) & set(q["expected_sources"]))
    return row


def rate(rows, key):
    vals = [r[key] for r in rows if r.get(key) is not None]
    return (sum(vals) / len(vals), len(vals)) if vals else (None, 0)


def fmt(rv):
    v, n = rv
    return "n/a" if v is None else f"{v * 100:.1f}% (n={n})"


# ------------------------------------------------------------------ main loop

async def run(args):
    questions = json.loads(Path(args.questions).read_text())
    if args.ids:
        questions = [q for q in questions if q["id"] in args.ids.split(",")]
    kb_files = [p.name for p in config.KB_DIR.rglob("*") if p.suffix.lower() in config.SUPPORTED_EXTENSIONS]

    model = args.model or config.LLM_MODEL
    desk = Helpdesk(args.mode, model)
    tag = f"{model.replace(':', '-').replace('/', '-')}_{args.mode}_{datetime.now():%Y%m%d_%H%M%S}"
    out_dir = config.RESULTS_DIR / tag
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"Evaluating {len(questions)} questions x {args.runs} runs | mode={args.mode} model={model}")

    records = []
    for run_no in range(1, args.runs + 1):
        for q in questions:
            t0 = time.time()
            try:
                ans = await desk.ask(q["question"], fresh_session=True)
                error = ""
            except Exception as e:  # keep going if one question crashes (e.g. malformed tool call)
                from helpdesk.session import Answer
                ans, error = Answer(text=f"ERROR: {e}"), str(e)
            rec = {"run": run_no, "id": q["id"], "category": q["category"], "question": q["question"],
                   "answer": ans.full_text, "agent": ans.agent, "tools": ans.tools_used,
                   "tool_calls": ans.tool_calls, "latency_s": round(time.time() - t0, 2), "error": error}
            rec.update(score(q, ans, kb_files))
            records.append(rec)
            flag = "REFUSED" if rec["refused"] else "answered"
            print(f"  run {run_no} {q['id']:<4} {rec['latency_s']:>6}s  {flag:<8} tools={rec['tools']}")

    # ---- stability across runs
    changed = []
    if args.runs > 1:
        for q in questions:
            rs = [r for r in records if r["id"] == q["id"]]
            verdicts = {(r["refused"], r["auto_correct"], r["tool_ok"]) for r in rs}
            sims = [SequenceMatcher(None, a["answer"], b["answer"]).ratio() for a, b in combinations(rs, 2)]
            min_sim = min(sims) if sims else 1.0
            if len(verdicts) > 1 or min_sim < args.sim_threshold:
                changed.append({"id": q["id"], "question": q["question"], "verdict_changed": len(verdicts) > 1,
                                "min_similarity": round(min_sim, 2), "answers": [r["answer"] for r in rs]})

    # ---- save raw + csv
    (out_dir / "records.json").write_text(json.dumps({"records": records, "changed": changed}, indent=2))
    cols = ["run", "id", "category", "question", "answer", "agent", "tools", "refused", "auto_correct",
            "manual_correct", "has_citation", "citation_valid", "citation_correct", "tool_ok", "route_ok",
            "cited", "retrieved_sources", "latency_s", "error"]
    with open(out_dir / "results.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in records:
            w.writerow({**r, "manual_correct": "", "tools": ";".join(r["tools"]),
                        "cited": ";".join(r["cited"]), "retrieved_sources": ";".join(r["retrieved_sources"])})

    # ---- summary
    in_scope = [r for r in records if r["correct_refusal"] is None]
    lines = [
        f"# Evaluation summary: {tag}", "",
        f"- Mode: **{args.mode}**, model: **{model}**, runs: {args.runs}, questions: {len(questions)}",
        f"- Temperature: {config.TEMPERATURE}, top_k: {config.TOP_K}, min_similarity: {config.MIN_SIMILARITY}", "",
        "| Metric | Value |", "|---|---|",
        f"| Answer accuracy (auto, keyword-based) | {fmt(rate(records, 'auto_correct'))} |",
        f"| Correct refusals (out-of-scope) | {fmt(rate(records, 'correct_refusal'))} |",
        f"| False refusals (in-scope) | {fmt(rate(records, 'false_refusal'))} |",
        f"| Answers with a citation | {fmt(rate(in_scope, 'has_citation'))} |",
        f"| Citations that match retrieved docs (grounded) | {fmt(rate(in_scope, 'citation_valid'))} |",
        f"| Correct source cited (vs expected_sources) | {fmt(rate(in_scope, 'citation_correct'))} |",
        f"| Correct tool used | {fmt(rate(records, 'tool_ok'))} |",
    ]
    if args.mode == "multi":
        lines.append(f"| Correct routing to specialist agent | {fmt(rate(records, 'route_ok'))} |")
    lines += [f"| Avg latency per question | {sum(r['latency_s'] for r in records) / len(records):.1f}s |",
              f"| Errors | {sum(1 for r in records if r['error'])} |", ""]

    lines.append("## Per category")
    lines.append("| Category | Accuracy (auto) | Refused | Tool OK |")
    lines.append("|---|---|---|---|")
    for cat in sorted({r["category"] for r in records}):
        rs = [r for r in records if r["category"] == cat]
        lines.append(f"| {cat} | {fmt(rate(rs, 'auto_correct'))} | {fmt(rate(rs, 'refused'))} | {fmt(rate(rs, 'tool_ok'))} |")

    lines += ["", f"## Questions whose answers changed across runs ({len(changed)})"]
    for c in changed:
        lines.append(f"- **{c['id']}** {c['question']} (verdict changed: {c['verdict_changed']}, "
                     f"min text similarity: {c['min_similarity']})")
    manual = sum(1 for r in records if r["auto_correct"] is None and r["correct_refusal"] is None and not r["refused"])
    lines += ["", f"_{manual} answers have no expected_keywords: grade them by hand in the "
                  f"`manual_correct` column of results.csv._"]

    summary = "\n".join(lines)
    (out_dir / "summary.md").write_text(summary)
    print("\n" + summary)
    print(f"\nSaved to {out_dir}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--mode", choices=["single", "multi"], default="multi")
    p.add_argument("--model", default=None)
    p.add_argument("--runs", type=int, default=3)
    p.add_argument("--questions", default=str(Path(__file__).parent / "questions.json"))
    p.add_argument("--ids", default="", help="comma separated subset, e.g. P01,S01,O01")
    p.add_argument("--sim-threshold", type=float, default=0.8,
                   help="answers less similar than this across runs are reported as 'changed'")
    asyncio.run(run(p.parse_args()))


if __name__ == "__main__":
    main()
