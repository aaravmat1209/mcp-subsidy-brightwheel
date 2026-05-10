"""
Main Pipeline - Multi-Agent Orchestration with Claude Router Pattern

Architecture:
  1. Claude multimodal: PDF/CSV → structured JSON (LLM justified)
  2. Claude orchestrator: Agentic tool calling with MCP (AI-driven decisions)
  3. Claude grader: quality evaluation (LLM justified)
  4. Rich report: terminal output

AGENTIC APPROACH:
  - Claude dynamically decides which MCP tools to call
  - No predetermined state machine (adaptive workflow)
  - Natural language reasoning for exceptions
  - Multi-agent coordination (extraction → orchestration → grading)

PRODUCTION DEPLOYMENT:
  - Lambda trigger on S3 upload (see infra/lambda_trigger.py)
  - Results write to DynamoDB audit table
  - SNS notification on completion
  - Sidekiq wrapper for Rails background jobs
"""

import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime

from src.agents.extraction_agent import extract
from src.agents.grader_agent import grade
from src.agents.orchestrator_agent import run_agentic_reconciliation


async def run(workflows: list[str] = None, dry_run: bool = True):
    """
    Main pipeline.

    Usage:
      python -m src.pipeline                    # runs all three workflows
      python -m src.pipeline kinderconnect      # single workflow
      python -m src.pipeline cacfp roster       # two workflows
    """
    print("=" * 70)
    print("BRIGHTWHEEL SUBSIDY RECONCILIATION PIPELINE")
    print("=" * 70)
    print()

    data_path = Path("data")
    results_path = Path("results")
    results_path.mkdir(exist_ok=True)

    file_map = {
        "kinderconnect": data_path / "kinderconnect_report.pdf",
        "cacfp": data_path / "cacfp_meal_count.pdf",
        "roster": data_path / "messy_roster.csv"
    }

    if not workflows:
        workflows = list(file_map.keys())

    print(f"Workflows: {', '.join(workflows)}")
    print(f"Dry run: {dry_run}")
    print()

    # ── Step 1: Extract (Claude multimodal) ──────────────────────────────
    print("[1/4] EXTRACTION (Claude multimodal)")
    print("-" * 70)

    extracted = {}
    for wf in workflows:
        file_path = file_map[wf]
        if not file_path.exists():
            print(f"  [SKIP] {wf}: file not found at {file_path}")
            continue

        print(f"  [extract] {wf} from {file_path.name}...", end=" ", flush=True)
        extracted[wf] = await extract(str(file_path))
        print(f"[OK] {len(extracted[wf])} records")

    print()

    # ── Step 2: Reconcile (Agentic Orchestrator with Claude) ─────────────
    print("[2/4] RECONCILIATION (Claude Agentic Orchestrator)")
    print("-" * 70)
    print("  Claude dynamically decides which MCP tools to call")
    print()

    results = {}
    for wf in extracted.keys():
        print(f"  [orchestrate] {wf} (Claude agent running)...", end=" ", flush=True)
        results[wf] = await run_agentic_reconciliation(wf, extracted[wf])
        summary = results[wf].get("summary", {})

        if wf == "kinderconnect":
            print(f"[OK] {summary.get('matched', 0)} matched, {summary.get('exceptions', 0)} exceptions")
        elif wf == "cacfp":
            print(f"[OK] {summary.get('valid', 0)} valid, {summary.get('non_payable', 0)} non-payable")
        elif wf == "roster":
            print(f"[OK] {summary.get('ready', 0)} ready, {summary.get('flagged', 0)} flagged")

    print()

    # ── Step 3: Grade (Claude evaluator) ──────────────────────────────────
    print("[3/4] GRADING (Claude quality check)")
    print("-" * 70)

    grades = {}
    for wf in results.keys():
        print(f"  [grade] {wf}...", end=" ", flush=True)
        grades[wf] = await grade(wf, extracted[wf], results[wf])
        g = grades[wf]
        status = "[PASS]" if g["pass"] else "[FAIL]"
        print(f"{status} score: {g['score']}/10")

    print()

    # ── Step 4: Report ────────────────────────────────────────────────────
    print("[4/4] REPORT")
    print("-" * 70)

    from src.report import print_report
    print_report(workflows, extracted, results, grades)

    # ── Save audit trail ──────────────────────────────────────────────────
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    audit_file = results_path / f"reconciliation_{timestamp}.json"

    with open(audit_file, "w") as f:
        json.dump({
            "timestamp": timestamp,
            "workflows": workflows,
            "extracted": extracted,
            "results": results,
            "grades": grades,
            "dry_run": dry_run
        }, f, indent=2)

    print()
    print(f"Audit trail saved: {audit_file}")
    print()

    # ── Summary ───────────────────────────────────────────────────────────
    total_time_saved = sum(results[wf]["summary"].get("time_saved_hours", 0) for wf in results.keys())
    print("=" * 70)
    print(f"COMPLETE: {total_time_saved:.1f} hours saved (~{total_time_saved*60:.0f} minutes)")
    print("=" * 70)


if __name__ == "__main__":
    args = sys.argv[1:]
    workflows = args if args else None
    asyncio.run(run(workflows))
