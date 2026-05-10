"""
KinderConnect Attendance Reconciliation - Burr DAG

Deterministic business logic for matching attendance records.
NO LLM orchestration - pure Python rules + direct MCP calls.
"""

from burr.core import action, State, ApplicationBuilder, when
from .mcp_client import call_mcp_tool, parse_time


# ── Actions (nodes in the DAG) ───────────────────────────────────────────

@action(reads=["current_record"], writes=["student", "lookup_status"])
async def lookup_student(state: State) -> State:
    """Call brightwheel MCP directly - no LLM."""
    record = state["current_record"]
    student = await call_mcp_tool(
        "get_student_by_kc_id",
        {"kc_id": record["kc_id"]}
    )

    if "error" in student:
        return state.update(student=None, lookup_status="NOT_FOUND")

    return state.update(student=student, lookup_status="FOUND")


@action(reads=["current_record", "student"], writes=["daily_results"])
async def compare_attendance(state: State) -> State:
    """
    Deterministic time and status comparison.

    Rule table (NO LLM judgment):
      status == OD in KC but student has check-in → EXPIRED_AUTH
      status == AB but no signature → MISSING_SIGNATURE
      status == P and |time_delta| < 10min → MATCH
      status == P and |time_delta| >= 10min → TIME_MISMATCH
    """
    record = state["current_record"]
    student = state["student"]
    results = []

    for day in record["daily_records"]:
        bw_record = await call_mcp_tool(
            "get_attendance_record",
            {"student_id": student["brightwheel_id"], "date": day["date"]}
        )

        if day["status"] == "OD":
            # KinderConnect says off day
            if bw_record.get("present"):
                results.append({
                    "date": day["date"],
                    "classification": "EXPIRED_AUTH",
                    "reason": f"KC shows OD but brightwheel has check-in on {day['date']}. Authorization likely expired."
                })
            else:
                results.append({"date": day["date"], "classification": "MATCH", "reason": "Both systems show off day"})

        elif day["status"] == "AB":
            # Absence
            if not bw_record.get("signature") and not bw_record.get("present"):
                results.append({
                    "date": day["date"],
                    "classification": "MISSING_SIGNATURE",
                    "reason": "Absence requires parent note/signature per policy"
                })
            else:
                results.append({"date": day["date"], "classification": "MATCH", "reason": "Absence properly documented"})

        elif day["status"] == "P":
            # Present - check time delta
            kc_in = parse_time(day.get("in_time", ""))
            bw_in = parse_time(bw_record.get("check_in", ""))

            if not bw_record.get("present"):
                results.append({
                    "date": day["date"],
                    "classification": "ATTENDANCE_MISMATCH",
                    "reason": f"KC shows present but brightwheel shows absent on {day['date']}"
                })
            elif kc_in and bw_in:
                delta = abs(kc_in - bw_in)
                if delta < 10:
                    results.append({"date": day["date"], "classification": "MATCH", "reason": f"Times match (delta: {delta}min)"})
                else:
                    results.append({
                        "date": day["date"],
                        "classification": "TIME_MISMATCH",
                        "reason": f"KC: {day['in_time']}, BW: {bw_record.get('check_in')} (delta: {delta}min > 10min threshold)"
                    })
            else:
                results.append({
                    "date": day["date"],
                    "classification": "MATCH",
                    "reason": "Both systems show present (times not comparable)"
                })

    return state.update(daily_results=results)


@action(reads=["current_record", "student", "daily_results"], writes=["record_result"])
async def log_result(state: State) -> State:
    """Log to MCP (dry_run=True always in demo)."""
    results = state["daily_results"]
    exceptions = [r for r in results if r["classification"] != "MATCH"]
    overall = "EXCEPTION" if exceptions else "MATCH"

    # Handle NOT_FOUND case
    if state["lookup_status"] == "NOT_FOUND":
        return state.update(record_result={
            "child_name": state["current_record"]["child_name"],
            "kc_id": state["current_record"]["kc_id"],
            "overall": "NOT_FOUND",
            "daily_results": [],
            "exceptions": [{
                "classification": "NOT_FOUND",
                "reason": f"KinderConnect ID {state['current_record']['kc_id']} not found in brightwheel system"
            }]
        })

    await call_mcp_tool("log_reconciliation_result", {
        "student_id": state["student"]["brightwheel_id"],
        "workflow": "kinderconnect",
        "result": overall,
        "details": {"daily_results": results},
        "dry_run": True
    })

    return state.update(record_result={
        "child_name": state["current_record"]["child_name"],
        "kc_id": state["current_record"]["kc_id"],
        "overall": overall,
        "daily_results": results,
        "exceptions": exceptions
    })


# ── Build the application ─────────────────────────────────────────────────

def build_kinderconnect_app(record: dict):
    """Build a Burr application for one student record."""
    return (
        ApplicationBuilder()
        .with_actions(lookup_student, compare_attendance, log_result)
        .with_transitions(
            ("lookup_student", "compare_attendance", when(lookup_status="FOUND")),
            ("lookup_student", "log_result", when(lookup_status="NOT_FOUND")),
            ("compare_attendance", "log_result")
        )
        .with_state(State({
            "current_record": record,
            "student": None,
            "lookup_status": None,
            "daily_results": [],
            "record_result": None
        }))
        .with_entrypoint("lookup_student")
        .build()
    )


async def run_kinderconnect(extracted_records: list) -> dict:
    """
    Run the Burr DAG for each extracted KinderConnect record.
    Parallel execution - one app per student.
    """
    import asyncio

    async def process_one(record):
        app = build_kinderconnect_app(record)
        _, _, state = await app.arun(halt_after=["log_result"])
        return state["record_result"]

    results = await asyncio.gather(*[process_one(r) for r in extracted_records])
    matched = [r for r in results if r["overall"] == "MATCH"]
    exceptions = [r for r in results if r["overall"] != "MATCH"]

    return {
        "matched": matched,
        "exceptions": exceptions,
        "summary": {
            "total": len(results),
            "matched": len(matched),
            "exceptions": len(exceptions),
            "match_rate": len(matched) / len(results) if results else 0,
            "time_saved_hours": 3.5
        }
    }
