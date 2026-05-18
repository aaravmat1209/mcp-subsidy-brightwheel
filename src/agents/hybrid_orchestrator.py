"""
Hybrid Orchestrator: Claude Decision-Making + Burr Batched Execution

Architecture:
1. Claude analyzes data and decides WHAT to reconcile
2. Dependency graph determines HOW to batch tool calls
3. Burr workflows execute batched operations
4. Claude synthesizes results with natural language insights
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Literal

from anthropic import Anthropic

from ..workflows.mcp_pool import call_mcp_tool

log = logging.getLogger(__name__)
client = Anthropic()

SUPPORTED_WORKFLOWS = Literal["kinderconnect", "cacfp", "roster"]


# ---------------------------------------------------------------------------
# Data classes — make structure explicit and IDE-friendly
# ---------------------------------------------------------------------------

@dataclass
class StudentPlan:
    kc_id: str
    child_name: str
    dates: list[str]
    priority: str = "normal"


@dataclass
class ReconciliationRecord:
    child_name: str
    kc_id: str
    brightwheel_id: str | None = None
    status: str = "NOT_FOUND"
    daily_results: list[dict] = field(default_factory=list)

    @property
    def found(self) -> bool:
        return self.status != "NOT_FOUND" and self.brightwheel_id is not None


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

_EMPTY_ID_VALUES = frozenset({None, "None", "null", "", "UNKNOWN"})


def validate_extracted_records(records: list[dict]) -> None:
    """Raise ValueError listing every record missing a valid kc_id."""
    missing = [
        r.get("child_name", "UNKNOWN")
        for r in records
        if r.get("kc_id") in _EMPTY_ID_VALUES
    ]
    if missing:
        raise ValueError(
            f"Extraction failed: kc_id is None/missing for {len(missing)} student(s): "
            f"{missing}\n"
            "Check the PDF format — KC IDs may be labelled differently or in a scanned region."
        )


# ---------------------------------------------------------------------------
# Claude helpers — thin wrappers so callers don't touch raw API details
# ---------------------------------------------------------------------------

def _call_claude(system: str, user: str, max_tokens: int = 4096) -> str:
    """Return the text of Claude's first content block."""
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=max_tokens,
        system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": user}],
    )
    return response.content[0].text


def _parse_json_response(raw: str) -> dict:
    """
    Extract the first top-level JSON object from a Claude response.

    Raises json.JSONDecodeError if nothing parseable is found.
    """
    start = raw.find("{")
    end = raw.rfind("}") + 1
    if start == -1 or end == 0:
        raise json.JSONDecodeError("No JSON object found", raw, 0)
    return json.loads(raw[start:end])


# ---------------------------------------------------------------------------
# Phase 1 — Planning
# ---------------------------------------------------------------------------

def _plan_reconciliation(records: list[dict]) -> tuple[list[StudentPlan], str]:
    """Ask Claude which students/dates to reconcile and how."""
    raw = _call_claude(
        system="You are a reconciliation planner. Output valid JSON only.",
        user=(
            f"Analyze these KinderConnect records and output a reconciliation plan.\n\n"
            f"Records:\n{json.dumps(records, indent=2)}\n\n"
            "Return JSON:\n"
            "{\n"
            '  "students": [\n'
            '    {"kc_id": "...", "child_name": "...", "dates": ["YYYY-MM-DD"], "priority": "normal"}\n'
            "  ],\n"
            '  "strategy": "batch_all" | "sequential_with_fallback"\n'
            "}"
        ),
        max_tokens=8000,
    )
    plan = _parse_json_response(raw)
    students = [StudentPlan(**s) for s in plan["students"]]
    log.info("Plan: %s for %d student(s)", plan["strategy"], len(students))
    return students, plan["strategy"]


# ---------------------------------------------------------------------------
# Phase 2 — Batched execution
# ---------------------------------------------------------------------------

async def _lookup_students(plans: list[StudentPlan]) -> dict[str, Any]:
    """
    Look up every student by kc_id in parallel.

    Returns a mapping kc_id → raw MCP result (or error dict).
    """
    async def _lookup(plan: StudentPlan) -> tuple[str, Any]:
        if not plan.kc_id or plan.kc_id in _EMPTY_ID_VALUES:
            return plan.kc_id, {"error": "MISSING_KC_ID", "child_name": plan.child_name}
        try:
            result = await call_mcp_tool("get_student_by_kc_id", {"kc_id": plan.kc_id})
            return plan.kc_id, result
        except Exception as exc:  # noqa: BLE001
            log.warning("Lookup failed for kc_id=%s: %s", plan.kc_id, exc)
            return plan.kc_id, {"error": str(exc)}

    pairs = await asyncio.gather(*[_lookup(p) for p in plans])
    return dict(pairs)


async def _fetch_attendance(
    plans: list[StudentPlan],
    students_by_kc_id: dict[str, Any],
) -> dict[tuple[str, str], Any]:
    """
    Fetch attendance for every (student, date) pair in parallel.

    Returns a mapping (kc_id, date) → raw MCP result.
    """
    async def _fetch(kc_id: str, brightwheel_id: str, date: str) -> tuple[tuple[str, str], Any]:
        try:
            result = await call_mcp_tool(
                "get_attendance_record",
                {"student_id": brightwheel_id, "date": date},
            )
            return (kc_id, date), result
        except Exception as exc:  # noqa: BLE001
            log.warning("Attendance fetch failed kc_id=%s date=%s: %s", kc_id, date, exc)
            return (kc_id, date), {"error": str(exc)}

    tasks = [
        _fetch(plan.kc_id, students_by_kc_id[plan.kc_id]["brightwheel_id"], date)
        for plan in plans
        for date in plan.dates
        if "error" not in students_by_kc_id.get(plan.kc_id, {"error": True})
    ]

    if not tasks:
        return {}

    pairs = await asyncio.gather(*tasks)
    return dict(pairs)


def _build_reconciliation_records(
    plans: list[StudentPlan],
    students_by_kc_id: dict[str, Any],
    attendance_by_key: dict[tuple[str, str], Any],
) -> list[ReconciliationRecord]:
    records = []
    for plan in plans:
        raw_student = students_by_kc_id.get(plan.kc_id, {"error": "NOT_FOUND"})
        if "error" in raw_student:
            records.append(ReconciliationRecord(child_name=plan.child_name, kc_id=plan.kc_id))
            continue

        daily = [
            {"date": date, "record": attendance_by_key[(plan.kc_id, date)]}
            for date in plan.dates
            if (plan.kc_id, date) in attendance_by_key
        ]
        records.append(
            ReconciliationRecord(
                child_name=plan.child_name,
                kc_id=plan.kc_id,
                brightwheel_id=raw_student["brightwheel_id"],
                status="CHECKED",
                daily_results=daily,
            )
        )
    return records


# ---------------------------------------------------------------------------
# Phase 3 — Synthesis (batched Claude calls)
# ---------------------------------------------------------------------------

_SYNTHESIS_SYSTEM = "You are a data reconciliation engine. Output only valid JSON."

_SYNTHESIS_RULES = """
- MATCH: Times within 10 minutes
- TIME_MISMATCH: Times differ by 10+ minutes → severity HIGH
- MISSING_STUDENT: Not found in Brightwheel → severity CRITICAL
"""

_SYNTHESIS_SCHEMA = """
{
  "matched": [],
  "exceptions": [
    {
      "child_name": "string",
      "kc_id": "string",
      "overall": "EXCEPTION",
      "exception_type": "TIME_MISMATCH | MISSING_STUDENT",
      "severity": "HIGH | CRITICAL",
      "action_required": "string",
      "exceptions": [{"date": "YYYY-MM-DD", "reason": "string"}]
    }
  ]
}
"""


def _synthesise_batch(
    extracted_batch: list[dict],
    reconciled_batch: list[ReconciliationRecord],
) -> dict:
    user_prompt = (
        f"Analyze the reconciliation data and classify each student.\n\n"
        f"<kinderconnect_records total=\"{len(extracted_batch)}\">\n"
        f"{json.dumps(extracted_batch, indent=2)}\n"
        f"</kinderconnect_records>\n\n"
        f"<brightwheel_reconciliation>\n"
        f"{json.dumps([r.__dict__ for r in reconciled_batch], indent=2)}\n"
        f"</brightwheel_reconciliation>\n\n"
        f"<classification_rules>{_SYNTHESIS_RULES}</classification_rules>\n\n"
        f"<output_schema>{_SYNTHESIS_SCHEMA}</output_schema>"
    )
    raw = _call_claude(system=_SYNTHESIS_SYSTEM, user=user_prompt)
    try:
        return _parse_json_response(raw)
    except json.JSONDecodeError:
        log.error("Synthesis JSON parse failed; falling back to manual classification")
        return _fallback_classify(reconciled_batch)


def _fallback_classify(records: list[ReconciliationRecord]) -> dict:
    """Conservative fallback when Claude's JSON is unparseable."""
    exceptions = [
        {
            "child_name": r.child_name,
            "kc_id": r.kc_id,
            "severity": "CRITICAL" if not r.found else "HIGH",
            "exception_type": "MISSING_STUDENT" if not r.found else "DATA_QUALITY_ISSUE",
            "action_required": (
                "Student in KinderConnect but not in Brightwheel."
                if not r.found
                else "Data quality issue — manual review required."
            ),
            "exceptions": r.daily_results,
        }
        for r in records
    ]
    return {"matched": [], "exceptions": exceptions}


def _synthesise_all(
    extracted_records: list[dict],
    reconciled_records: list[ReconciliationRecord],
    batch_size: int = 10,
) -> tuple[list[dict], list[dict]]:
    matched: list[dict] = []
    exceptions: list[dict] = []

    for batch_start in range(0, len(extracted_records), batch_size):
        ext_batch = extracted_records[batch_start : batch_start + batch_size]
        rec_batch = reconciled_records[batch_start : batch_start + batch_size]
        batch_num = batch_start // batch_size + 1

        result = _synthesise_batch(ext_batch, rec_batch)
        matched.extend(result.get("matched", []))
        exceptions.extend(result.get("exceptions", []))
        log.info("Synthesis batch %d: %d matched, %d exceptions", batch_num, len(result.get("matched", [])), len(result.get("exceptions", [])))

    return matched, exceptions


# ---------------------------------------------------------------------------
# Phase 4 — Actions
# ---------------------------------------------------------------------------

def _agency_amount_for(
    kc_id: str,
    extracted_records: list[dict],
    raw_student: dict,
    fallback_daily_rate: float = 40.0,
) -> float:
    """Resolve agency payment amount from invoice data or attendance count."""
    for invoice in raw_student.get("open_invoices", []):
        for payer in invoice.get("payers", []):
            if payer.get("payer_type") == "agency" and payer.get("amount_due", 0) > 0:
                return payer["amount_due"]

    # Fallback: count days present × daily rate
    for rec in extracted_records:
        if rec.get("kc_id") == kc_id:
            days = sum(
                1 for d in rec.get("daily_records", []) if d.get("status") == "P"
            )
            return days * fallback_daily_rate

    return 0.0


def _underpayment_amount(exception: dict, raw_student: dict) -> float:
    """Estimate the parent balance transfer for a time-mismatch exception."""
    expected = 0.0
    for invoice in raw_student.get("open_invoices", []):
        for payer in invoice.get("payers", []):
            if payer.get("payer_type") == "agency":
                expected = payer.get("amount_due", 0.0)
        if expected:
            break

    mismatched_days = len(exception.get("exceptions", []))
    shortfall = mismatched_days * 10.0
    # Cap shortfall at 10 % of expected agency payment to avoid over-billing
    cap = expected * 0.10
    return min(shortfall, cap) if cap > 0 else shortfall


async def _stage_actions_for_matches(
    matched: list[dict],
    records_by_kc_id: dict[str, ReconciliationRecord],
    students_by_kc_id: dict[str, Any],
    extracted_records: list[dict],
    payment_date: str,
) -> list[dict]:
    async def _stage(match: dict) -> dict | None:
        kc_id = match.get("kc_id")
        rec = records_by_kc_id.get(kc_id)
        raw_student = students_by_kc_id.get(kc_id, {})

        if not rec or not rec.brightwheel_id or "error" in raw_student:
            return None

        amount = _agency_amount_for(kc_id, extracted_records, raw_student)
        result = await call_mcp_tool(
            "log_agency_payment",
            {
                "student_id": rec.brightwheel_id,
                "amount": amount,
                "date": payment_date,
                "agency_id": "STATE-KINDERCONNECT",
                "dry_run": True,
            },
        )
        return result.get("action") if result.get("status") == "staged" else None

    results = await asyncio.gather(*[_stage(m) for m in matched])
    return [r for r in results if r is not None]


async def _stage_actions_for_exceptions(
    exceptions: list[dict],
    records_by_kc_id: dict[str, ReconciliationRecord],
    students_by_kc_id: dict[str, Any],
    document_due_date: str,
) -> list[dict]:
    staged = []

    for exc in exceptions:
        kc_id = exc.get("kc_id")
        rec = records_by_kc_id.get(kc_id)
        raw_student = students_by_kc_id.get(kc_id, {})

        if not rec or not rec.brightwheel_id:
            log.info("Skipping action for %s — not in Brightwheel", exc.get("child_name"))
            continue

        exc_type = exc.get("exception_type")
        action_note = exc.get("action_required", "")

        if exc_type == "TIME_MISMATCH" and exc.get("severity") in {"HIGH", "CRITICAL"}:
            amount = _underpayment_amount(exc, raw_student)
            result = await call_mcp_tool(
                "bill_another_payer",
                {
                    "student_id": rec.brightwheel_id,
                    "remaining_balance": amount,
                    "payer_type": "parent_copay",
                    "reason": f"State underpaid due to time discrepancies. {action_note}",
                    "dry_run": True,
                },
            )

        elif "auth" in action_note.lower() or "authorization" in action_note.lower():
            result = await call_mcp_tool(
                "create_document_request",
                {
                    "student_id": rec.brightwheel_id,
                    "document_type": "eligibility_letter",
                    "reason": f"Authorization may have expired. {action_note}",
                    "due_date": document_due_date,
                    "dry_run": True,
                },
            )
        else:
            continue

        if result.get("status") == "staged" and result.get("action"):
            staged.append(result["action"])

    return staged


# ---------------------------------------------------------------------------
# Top-level entry points
# ---------------------------------------------------------------------------

async def hybrid_reconcile_kinderconnect(extracted_records: list[dict]) -> dict:
    """
    Hybrid KinderConnect reconciliation.

    Phase 1 — Claude plans which students/dates to check.
    Phase 2 — Batch-parallel MCP calls (lookups + attendance).
    Phase 3 — Claude classifies results in batches.
    Phase 4 — Auto-stage Brightwheel actions.
    """
    validate_extracted_records(extracted_records)

    # Phase 1
    log.info("[Phase 1] Planning for %d student(s)…", len(extracted_records))
    plans, strategy = _plan_reconciliation(extracted_records)

    # Phase 2
    log.info("[Phase 2] Executing batched MCP calls (strategy=%s)…", strategy)
    students_by_kc_id = await _lookup_students(plans)
    attendance_by_key = await _fetch_attendance(plans, students_by_kc_id)
    reconciled = _build_reconciliation_records(plans, students_by_kc_id, attendance_by_key)

    log.info(
        "[Phase 2] %d lookup(s), %d attendance record(s)",
        len(students_by_kc_id),
        len(attendance_by_key),
    )

    # Phase 3
    log.info("[Phase 3] Synthesising results…")
    matched, exceptions = _synthesise_all(extracted_records, reconciled)

    # Build lookup maps for Phase 4
    records_by_kc_id = {r.kc_id: r for r in reconciled}

    # Phase 4
    log.info("[Phase 4] Staging actions…")
    payment_date = "2026-05-09"       # TODO: derive from records or pass as parameter
    document_due_date = "2026-05-20"  # TODO: derive from policy config

    match_actions, exc_actions = await asyncio.gather(
        _stage_actions_for_matches(
            matched, records_by_kc_id, students_by_kc_id, extracted_records, payment_date
        ),
        _stage_actions_for_exceptions(
            exceptions, records_by_kc_id, students_by_kc_id, document_due_date
        ),
    )
    staged_actions = match_actions + exc_actions

    total = len(extracted_records)
    summary = {
        "total_students": total,
        "matched_children": len(matched),
        "exception_children": len(exceptions),
        "match_rate": round(len(matched) / total * 100, 1) if total else 0.0,
        "time_saved_hours": round(total * 15 / 60, 1),
        "actions_staged": len(staged_actions),
    }

    log.info(
        "[Done] %d matched, %d exceptions, %d action(s) staged",
        summary["matched_children"],
        summary["exception_children"],
        summary["actions_staged"],
    )

    return {
        "matched": matched,
        "exceptions": exceptions,
        "summary": summary,
        "staged_actions": staged_actions,
    }


async def hybrid_reconcile(
    workflow: SUPPORTED_WORKFLOWS,
    extracted_records: list[dict],
) -> dict:
    """Entry point. Routes to the correct workflow handler."""
    if workflow == "kinderconnect":
        return await hybrid_reconcile_kinderconnect(extracted_records)

    # CACFP and Roster: deterministic Burr workflows, no Claude synthesis.
    # TODO: replace placeholder slices with real Burr workflow calls.
    if workflow == "cacfp":
        time_saved = len(extracted_records) * 10 / 60
        return {
            "valid": [],        # populated by Burr
            "non_payable": [],  # populated by Burr
            "summary": {
                "total": len(extracted_records),
                "time_saved_hours": round(time_saved, 1),
            },
        }

    if workflow == "roster":
        time_saved = len(extracted_records) * 5 / 60
        return {
            "ready": [],    # populated by Burr
            "flagged": [],  # populated by Burr
            "summary": {
                "total": len(extracted_records),
                "time_saved_hours": round(time_saved, 1),
            },
        }

    raise ValueError(f"Unknown workflow: {workflow!r}")
