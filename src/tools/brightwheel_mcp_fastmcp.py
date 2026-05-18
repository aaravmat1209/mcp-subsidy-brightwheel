"""
Brightwheel Billing MCP Server - FastMCP Version

Mirrors mcp-atlassian architecture:
- Single long-running server
- Connection pooling via lifespan
- FastMCP for cleaner code
- SSE transport option for remote access

PRODUCTION SWAP:
- Data source: JSON file → PostgreSQL queries
"""

import json
from pathlib import Path
from typing import Any
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastmcp import FastMCP, Context

# Database path - use the large dataset
DB_PATH = Path(__file__).parent.parent.parent / "data" / "brightwheel_database_large.json"


class BrightwheelDBContext:
    """Context holding the database connection (like Jira/Confluence clients in mcp-atlassian)."""

    def __init__(self):
        self.db = self.load_db()

    def load_db(self) -> dict:
        """Load database. In production: PostgreSQL connection pool."""
        with open(DB_PATH) as f:
            return json.load(f)

    def normalize_name(self, name: str) -> str:
        """Normalize name for comparison."""
        name = name.replace(",", "").strip().lower()
        parts = [p.strip() for p in name.split() if p.strip()]
        return " ".join(parts)


@asynccontextmanager
async def brightwheel_lifespan(app: FastMCP[BrightwheelDBContext]) -> AsyncIterator[BrightwheelDBContext]:
    """Initialize database connection once (like mcp-atlassian's Jira/Confluence clients)."""
    print("[Brightwheel MCP] Starting server...")
    context = BrightwheelDBContext()
    print(f"[Brightwheel MCP] Loaded {len(context.db['students'])} students from database")
    yield context
    print("[Brightwheel MCP] Shutting down...")


# Initialize FastMCP server with lifespan
mcp = FastMCP(
    name="brightwheel-billing",
    lifespan=brightwheel_lifespan
)


@mcp.tool()
async def get_student_by_kc_id(ctx: Context, kc_id: str) -> dict:
    """Look up student by KinderConnect ID (e.g., '987654321')."""
    db_context = ctx.request_context.lifespan_context

    for student in db_context.db["students"]:
        db_kc_id = student.get("kinderconnect_id")
        if db_kc_id == kc_id:
            return student

    return {"error": "NOT_FOUND", "kc_id": kc_id}


@mcp.tool()
async def get_student_by_name(ctx: Context, name: str) -> dict:
    """Look up student by name (handles 'Last, First' or 'First Last')."""
    db_context = ctx.request_context.lifespan_context
    normalized_input = db_context.normalize_name(name)
    input_parts = set(normalized_input.split())

    for student in db_context.db["students"]:
        full_name = f"{student.get('first_name', '')} {student.get('last_name', '')}"
        db_parts = set(db_context.normalize_name(full_name).split())

        if input_parts == db_parts:
            return student

    return {"error": "NOT_FOUND", "name": name}


@mcp.tool()
async def get_attendance_record(ctx: Context, student_id: str, date: str) -> dict:
    """Get attendance record for a student on a specific date."""
    db_context = ctx.request_context.lifespan_context
    for student in db_context.db["students"]:
        if student.get("brightwheel_id") == student_id:
            check_ins = student.get("check_ins", {})
            if date in check_ins:
                record = check_ins[date]
                return {
                    "present": True,
                    "check_in": record.get("in"),
                    "check_out": record.get("out"),
                    "signature": record.get("signature", False),
                    "meals_served": student.get("meals_served", {}).get(date, [])
                }
            else:
                return {"present": False, "date": date}

    return {"error": "STUDENT_NOT_FOUND", "student_id": student_id}


@mcp.tool()
async def get_meal_authorizations(ctx: Context, student_id: str) -> dict:
    """Get meal authorizations for a student."""
    db_context = ctx.request_context.lifespan_context
    for student in db_context.db["students"]:
        if student.get("brightwheel_id") == student_id:
            meal_auth = student.get("meal_authorizations", {})
            return {
                "student_id": student_id,
                "frp_category": student.get("frp_category"),
                "authorized_meals": [k for k, v in meal_auth.items() if v],
                "supper_authorized": meal_auth.get("supper", False)
            }

    return {"error": "STUDENT_NOT_FOUND", "student_id": student_id}


@mcp.tool()
async def get_open_invoices(ctx: Context, case_id: str) -> dict:
    """Get open invoices for a student by case ID."""
    db_context = ctx.request_context.lifespan_context
    for student in db_context.db["students"]:
        if student.get("kinderconnect_id") == case_id:
            return {
                "student_id": student.get("brightwheel_id"),
                "case_id": case_id,
                "invoices": student.get("open_invoices", [])
            }

    return {"error": "NOT_FOUND", "case_id": case_id}


@mcp.tool()
async def log_reconciliation_result(
    ctx: Context,
    student_id: str,
    workflow: str,
    result: str,
    details: dict,
    dry_run: bool = True
) -> dict:
    """Log a reconciliation result (always dry_run=True in demo)."""
    return {
        "would_write": {
            "student_id": student_id,
            "workflow": workflow,
            "result": result,
            "details": details,
            "timestamp": "2026-05-10T12:00:00Z"
        },
        "dry_run": dry_run,
        "note": "In production, this would write to brightwheel billing DB"
    }


@mcp.tool()
async def get_agency_summary(ctx: Context, agency_name: str) -> dict:
    """Get summary statistics for an agency."""
    db_context = ctx.request_context.lifespan_context
    students_with_agency = []
    total_expected = 0.0
    total_received = 0.0
    open_invoices_count = 0

    for student in db_context.db["students"]:
        for invoice in student.get("open_invoices", []):
            for payer in invoice.get("payers", []):
                if payer.get("payer_name") == agency_name:
                    students_with_agency.append(student.get("brightwheel_id"))
                    total_expected += payer.get("amount_due", 0)
                    total_received += payer.get("amount_paid", 0)
                    if payer.get("status") == "open":
                        open_invoices_count += 1

    return {
        "agency_name": agency_name,
        "total_students": len(set(students_with_agency)),
        "total_expected": total_expected,
        "total_received": total_received,
        "balance_due": total_expected - total_received,
        "open_invoices_count": open_invoices_count
    }


# ========================================
# WRITE-ENABLED TOOLS: System of Action
# ========================================

@mcp.tool()
async def log_agency_payment(
    ctx: Context,
    student_id: str,
    amount: float,
    date: str,
    agency_id: str,
    dry_run: bool = True
) -> dict:
    """
    Log a subsidy payment received from state agency.

    This is the "System of Action" - automatically stages payment logging
    when reconciliation shows a MATCH between state report and Brightwheel attendance.

    In production: POST to /api/billing/log_payment
    """
    db_context = ctx.request_context.lifespan_context

    # Find student
    student = None
    for s in db_context.db["students"]:
        if s.get("brightwheel_id") == student_id:
            student = s
            break

    if not student:
        return {"error": "STUDENT_NOT_FOUND", "student_id": student_id}

    # Calculate invoice ID (would be actual invoice lookup in production)
    invoice_id = f"INV-{student_id}-{date[:7]}"  # e.g., INV-BW-1001-2026-05

    action = {
        "action_type": "log_agency_payment",
        "student_id": student_id,
        "student_name": f"{student.get('first_name')} {student.get('last_name')}",
        "amount": amount,
        "date": date,
        "agency_id": agency_id,
        "invoice_id": invoice_id,
        "timestamp": "2026-05-10T12:00:00Z"
    }

    if dry_run:
        return {
            "status": "staged",
            "message": f"Payment of ${amount} staged for approval",
            "action": action,
            "dry_run": True,
            "next_step": "Admin reviews in 'Staged Actions' and clicks 'Approve All'"
        }
    else:
        # Production: Update invoice in database
        return {
            "status": "payment_logged",
            "invoice_id": invoice_id,
            "amount_applied": amount,
            "new_balance": 0.0,
            "action": action
        }


@mcp.tool()
async def bill_another_payer(
    ctx: Context,
    student_id: str,
    remaining_balance: float,
    payer_type: str,
    reason: str,
    dry_run: bool = True
) -> dict:
    """
    Transfer remaining balance to another payer (usually parent co-pay).

    This handles the "Underpayment" scenario: State paid $200 but expected $220,
    so the remaining $20 gets billed to parent as co-pay.

    In production: POST to /api/billing/transfer_balance
    """
    db_context = ctx.request_context.lifespan_context

    # Find student
    student = None
    for s in db_context.db["students"]:
        if s.get("brightwheel_id") == student_id:
            student = s
            break

    if not student:
        return {"error": "STUDENT_NOT_FOUND", "student_id": student_id}

    # Get parent info (in production, would be proper parent lookup)
    parent_payer_id = f"PARENT-{student_id}"

    action = {
        "action_type": "bill_another_payer",
        "student_id": student_id,
        "student_name": f"{student.get('first_name')} {student.get('last_name')}",
        "remaining_balance": remaining_balance,
        "payer_type": payer_type,
        "payer_id": parent_payer_id,
        "reason": reason,
        "timestamp": "2026-05-10T12:00:00Z"
    }

    if dry_run:
        return {
            "status": "staged",
            "message": f"Balance transfer of ${remaining_balance} to {payer_type} staged for approval",
            "action": action,
            "dry_run": True,
            "next_step": "Admin reviews and clicks 'Approve All'"
        }
    else:
        # Production: Create new invoice line item
        return {
            "status": "balance_transferred",
            "new_payer": parent_payer_id,
            "amount": remaining_balance,
            "invoice_created": f"INV-{parent_payer_id}-COPAY",
            "action": action
        }


@mcp.tool()
async def create_document_request(
    ctx: Context,
    student_id: str,
    document_type: str,
    reason: str,
    due_date: str = None,
    dry_run: bool = True
) -> dict:
    """
    Request new document from parent (e.g., eligibility letter after auth expires).

    This handles the "Auth Expired" scenario: State report shows authorization ended,
    so we proactively request parent to upload new eligibility letter.

    In production: POST to /api/documents/request
    """
    db_context = ctx.request_context.lifespan_context

    # Find student
    student = None
    for s in db_context.db["students"]:
        if s.get("brightwheel_id") == student_id:
            student = s
            break

    if not student:
        return {"error": "STUDENT_NOT_FOUND", "student_id": student_id}

    # Get parent contact info (in production, proper parent lookup)
    parent_email = f"parent.{student.get('last_name', 'unknown').lower()}@example.com"

    action = {
        "action_type": "create_document_request",
        "student_id": student_id,
        "student_name": f"{student.get('first_name')} {student.get('last_name')}",
        "document_type": document_type,
        "reason": reason,
        "parent_email": parent_email,
        "due_date": due_date or "2026-05-20",
        "timestamp": "2026-05-10T12:00:00Z"
    }

    if dry_run:
        return {
            "status": "staged",
            "message": f"Document request for '{document_type}' staged for approval",
            "action": action,
            "dry_run": True,
            "next_step": "Admin reviews and clicks 'Approve All' to send request"
        }
    else:
        # Production: Send email/notification to parent
        return {
            "status": "request_sent",
            "request_id": f"DOC-{student_id}-{document_type}",
            "sent_to": parent_email,
            "due_date": due_date or "2026-05-20",
            "action": action
        }


if __name__ == "__main__":
    # Run with stdio transport (for MCP clients)
    # For remote access, use: mcp.run(transport="sse", port=8001)
    mcp.run(transport="stdio")
