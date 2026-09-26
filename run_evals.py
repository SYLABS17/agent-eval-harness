"""Run every golden case through the agent, grade it, print a table and save the results.

    python run_evals.py               normal run
    python run_evals.py --seed-leak   switch the access filter off to prove the harness notices

Exit code is 1 if any permission check fails. Permission failures block release.
"""

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

import tools
from agent import run_agent
from config import MODEL
from graders import grade_citations, grade_permission, grade_tool

ROOT = Path(__file__).parent
CASES_PATH = ROOT / "evals" / "golden_v1.jsonl"
RESULTS_DIR = ROOT / "results"


def load_cases():
    with CASES_PATH.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def mark(passed):
    return "pass" if passed else "FAIL"


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--seed-leak", action="store_true",
        help="disable the access filter in tools.py to demonstrate a caught leak",
    )
    args = parser.parse_args()
    if args.seed_leak:
        tools.SEED_LEAK = True

    load_dotenv()
    if os.environ.get("ANTHROPIC_API_KEY", "replace-me") == "replace-me":
        sys.exit("ANTHROPIC_API_KEY is not set. Put your key in .env (see .env.example).")

    cases = load_cases()
    rows = []
    print(f"model={MODEL}  cases={len(cases)}  seed_leak={tools.SEED_LEAK}\n")
    print(f"{'id':<5} {'category':<11} {'TOOL':<5} {'CITE':<5} {'PERM':<5} overall")
    print("-" * 45)
    for case in cases:
        session = {"role": case["role"], "employee_id": case["employee_id"]}
        result = run_agent(case["question"], session)
        grades = {
            "tool": grade_tool(case, result),
            "citations": grade_citations(case, result),
            "permission": grade_permission(case, result),
        }
        passed = all(ok for ok, _ in grades.values())
        print(
            f"{case['id']:<5} {case['category']:<11} {mark(grades['tool'][0]):<5} "
            f"{mark(grades['citations'][0]):<5} {mark(grades['permission'][0]):<5} {mark(passed)}",
            flush=True,
        )
        rows.append({
            **case,
            "answer": result["answer"],
            "tools_called": result["tools_called"],
            "retrieved_ids": result["retrieved_ids"],
            "grades": {name: {"passed": ok, "reason": why} for name, (ok, why) in grades.items()},
            "passed": passed,
        })

    # Say why anything failed, so the table is actionable.
    failures = [
        (row["id"], name, grade["reason"])
        for row in rows for name, grade in row["grades"].items() if not grade["passed"]
    ]
    if failures:
        print("\nfailures:")
        for case_id, name, reason in failures:
            print(f"  {case_id} {name}: {reason}")

    # Pass rates per category (in order of first appearance) and overall.
    by_category = {}
    for row in rows:
        by_category.setdefault(row["category"], []).append(row["passed"])
    summary = {
        "per_category": {c: f"{sum(v)}/{len(v)}" for c, v in by_category.items()},
        "overall": f"{sum(r['passed'] for r in rows)}/{len(rows)}",
        "permission_failures": [r["id"] for r in rows if not r["grades"]["permission"]["passed"]],
    }
    print("\npass rates:")
    for category, outcomes in by_category.items():
        print(f"  {category:<11} {sum(outcomes)}/{len(outcomes)}  ({100 * sum(outcomes) / len(outcomes):.0f}%)")
    n_pass = sum(r["passed"] for r in rows)
    print(f"  {'overall':<11} {n_pass}/{len(rows)}  ({100 * n_pass / len(rows):.0f}%)")

    RESULTS_DIR.mkdir(exist_ok=True)
    suffix = "_seedleak" if tools.SEED_LEAK else ""
    out_path = RESULTS_DIR / f"{date.today().isoformat()}_{MODEL}{suffix}.json"
    out_path.write_text(
        json.dumps(
            {"date": date.today().isoformat(), "model": MODEL, "seed_leak": tools.SEED_LEAK,
             "summary": summary, "cases": rows},
            indent=2, ensure_ascii=False,
        ) + "\n",
        encoding="utf-8",
    )
    print(f"\nsaved {out_path.relative_to(ROOT)}")

    if summary["permission_failures"]:
        print(f"PERMISSION FAILURES in {summary['permission_failures']}: release blocked.")
        sys.exit(1)
    print("no permission failures")


if __name__ == "__main__":
    main()
