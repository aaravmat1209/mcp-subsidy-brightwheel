"""
Brightwheel Billing MCP Server

This MCP server provides tools for subsidy reconciliation workflows.
Mirrors the structure of brightwheel/mcp-atlassian.

PRODUCTION SWAP:
- Transport: stdio_server → SSE transport for remote access
- Data source: JSON file → PostgreSQL queries to brightwheel billing DB
- Same tool definitions, different implementation backend
"""

import asyncio
import json
from pathlib import Path
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

# Database path
DB_PATH = Path(__file__).parent.parent.parent / "data" / "brightwheel_database.json"


def load_db() -> dict:
    """
    Load student database from JSON file.

    PRODUCTION SWAP: Replace with PostgreSQL connection
    - import psycopg2
    - conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    - return cursor queries instead of JSON
    """
    with open(DB_PATH) as f:
        return json.load(f)


# Initialize MCP server
server = Server("brightwheel-billing")


def normalize_name(name: str) -> str:
    """
    Normalize name for comparison.
    Handles "Rodriguez, Emma" and "Emma Rodriguez" → "emma rodriguez"
    """
    # Remove commas and extra spaces, convert to lowercase
    name = name.replace(",", "").strip().lower()
    parts = [p.strip() for p in name.split() if p.strip()]

    if len(parts) >= 2:
        # If looks like "last first", swap to "first last"
        # Just normalize to consistent format
        return " ".join(parts)
    return name


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List all available billing tools."""
    return [
        Tool(
            name="get_student_by_kc_id",
            description="Look up student by KinderConnect ID (e.g., '987654321')",
            inputSchema={
                "type": "object",
                "properties": {
                    "kc_id": {"type": "string", "description": "KinderConnect ID"}
                },
                "required": ["kc_id"]
            }
        ),
        Tool(
            name="get_student_by_name",
            description="Look up student by name (handles 'Last, First' or 'First Last')",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Student name"}
                },
                "required": ["name"]
            }
        ),
        Tool(
            name="get_attendance_record",
            description="Get attendance record for a student on a specific date",
            inputSchema={
                "type": "object",
                "properties": {
                    "student_id": {"type": "string", "description": "Brightwheel student ID (e.g., 'BW-1001')"},
                    "date": {"type": "string", "description": "Date in YYYY-MM-DD format"}
                },
                "required": ["student_id", "date"]
            }
        ),
        Tool(
            name="get_meal_authorizations",
            description="Get meal authorizations for a student",
            inputSchema={
                "type": "object",
                "properties": {
                    "student_id": {"type": "string", "description": "Brightwheel student ID"}
                },
                "required": ["student_id"]
            }
        ),
        Tool(
            name="get_open_invoices",
            description="Get open invoices for a student by case ID",
            inputSchema={
                "type": "object",
                "properties": {
                    "case_id": {"type": "string", "description": "KinderConnect case ID (e.g., 'KC-1042')"}
                },
                "required": ["case_id"]
            }
        ),
        Tool(
            name="log_reconciliation_result",
            description="Log a reconciliation result (always dry_run=True in demo)",
            inputSchema={
                "type": "object",
                "properties": {
                    "student_id": {"type": "string"},
                    "workflow": {"type": "string", "enum": ["kinderconnect", "cacfp", "roster"]},
                    "result": {"type": "string", "enum": ["MATCH", "EXCEPTION"]},
                    "details": {"type": "object"},
                    "dry_run": {"type": "boolean", "default": True}
                },
                "required": ["student_id", "workflow", "result", "details"]
            }
        ),
        Tool(
            name="get_agency_summary",
            description="Get summary statistics for an agency",
            inputSchema={
                "type": "object",
                "properties": {
                    "agency_name": {"type": "string", "description": "Agency name (e.g., 'Texas CCSP')"}
                },
                "required": ["agency_name"]
            }
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: Any) -> list[TextContent]:
    """
    Handle tool calls.
    Returns list[TextContent] with JSON string (mcp-atlassian pattern).
    """
    db = load_db()

    if name == "get_student_by_kc_id":
        kc_id = arguments["kc_id"]
        # PRODUCTION SWAP: SELECT * FROM students WHERE kinderconnect_id = %s
        for student in db["students"]:
            if student.get("kinderconnect_id") == kc_id:
                return [TextContent(type="text", text=json.dumps(student, indent=2))]

        error = {"error": "NOT_FOUND", "kc_id": kc_id}
        return [TextContent(type="text", text=json.dumps(error, indent=2))]

    elif name == "get_student_by_name":
        name_input = arguments["name"]
        normalized_input = normalize_name(name_input)
        # Split to handle both "First Last" and "Last, First" orderings
        input_parts = set(normalized_input.split())

        # PRODUCTION SWAP: SELECT * FROM students WHERE LOWER(first_name || ' ' || last_name) LIKE %s
        for student in db["students"]:
            full_name = f"{student.get('first_name', '')} {student.get('last_name', '')}"
            db_parts = set(normalize_name(full_name).split())

            # Match if all name parts are present (handles any order)
            if input_parts == db_parts:
                return [TextContent(type="text", text=json.dumps(student, indent=2))]

        error = {"error": "NOT_FOUND", "name": name_input}
        return [TextContent(type="text", text=json.dumps(error, indent=2))]

    elif name == "get_attendance_record":
        student_id = arguments["student_id"]
        date = arguments["date"]

        # PRODUCTION SWAP: SELECT * FROM attendance WHERE student_id = %s AND date = %s
        for student in db["students"]:
            if student.get("brightwheel_id") == student_id:
                check_ins = student.get("check_ins", {})
                if date in check_ins:
                    record = check_ins[date]
                    result = {
                        "present": True,
                        "check_in": record.get("in"),
                        "check_out": record.get("out"),
                        "signature": record.get("signature", False),
                        "meals_served": student.get("meals_served", {}).get(date, [])
                    }
                    return [TextContent(type="text", text=json.dumps(result, indent=2))]
                else:
                    result = {"present": False, "date": date}
                    return [TextContent(type="text", text=json.dumps(result, indent=2))]

        error = {"error": "STUDENT_NOT_FOUND", "student_id": student_id}
        return [TextContent(type="text", text=json.dumps(error, indent=2))]

    elif name == "get_meal_authorizations":
        student_id = arguments["student_id"]

        # PRODUCTION SWAP: SELECT * FROM meal_authorizations WHERE student_id = %s
        for student in db["students"]:
            if student.get("brightwheel_id") == student_id:
                meal_auth = student.get("meal_authorizations", {})
                result = {
                    "student_id": student_id,
                    "frp_category": student.get("frp_category"),
                    "authorized_meals": [k for k, v in meal_auth.items() if v],
                    "supper_authorized": meal_auth.get("supper", False)
                }
                return [TextContent(type="text", text=json.dumps(result, indent=2))]

        error = {"error": "STUDENT_NOT_FOUND", "student_id": student_id}
        return [TextContent(type="text", text=json.dumps(error, indent=2))]

    elif name == "get_open_invoices":
        case_id = arguments["case_id"]

        # PRODUCTION SWAP: SELECT * FROM invoices WHERE case_id = %s AND status = 'open'
        for student in db["students"]:
            if student.get("kinderconnect_id") == case_id:
                invoices = student.get("open_invoices", [])
                result = {
                    "student_id": student.get("brightwheel_id"),
                    "case_id": case_id,
                    "invoices": invoices
                }
                return [TextContent(type="text", text=json.dumps(result, indent=2))]

        error = {"error": "NOT_FOUND", "case_id": case_id}
        return [TextContent(type="text", text=json.dumps(error, indent=2))]

    elif name == "log_reconciliation_result":
        # PRODUCTION SWAP: INSERT INTO reconciliation_log (...) VALUES (...)
        result = {
            "would_write": {
                "student_id": arguments["student_id"],
                "workflow": arguments["workflow"],
                "result": arguments["result"],
                "details": arguments["details"],
                "timestamp": "2026-05-09T22:50:00Z"
            },
            "dry_run": arguments.get("dry_run", True),
            "note": "In production, this would write to brightwheel billing DB"
        }
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "get_agency_summary":
        agency_name = arguments["agency_name"]

        # PRODUCTION SWAP: Complex aggregation query across invoices table
        students_with_agency = []
        total_expected = 0.0
        total_received = 0.0
        open_invoices_count = 0

        for student in db["students"]:
            for invoice in student.get("open_invoices", []):
                for payer in invoice.get("payers", []):
                    if payer.get("payer_name") == agency_name:
                        students_with_agency.append(student.get("brightwheel_id"))
                        total_expected += payer.get("amount_due", 0)
                        total_received += payer.get("amount_paid", 0)
                        if payer.get("status") == "open":
                            open_invoices_count += 1

        result = {
            "agency_name": agency_name,
            "total_students": len(set(students_with_agency)),
            "total_expected": total_expected,
            "total_received": total_received,
            "balance_due": total_expected - total_received,
            "open_invoices_count": open_invoices_count
        }
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    else:
        error = {"error": "UNKNOWN_TOOL", "tool": name}
        return [TextContent(type="text", text=json.dumps(error, indent=2))]


async def main():
    """Run the MCP server via stdio transport."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())
