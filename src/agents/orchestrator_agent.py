"""
Agentic Orchestrator - Claude Router Pattern

Multi-agent system where Claude dynamically decides which MCP tools to call
based on the reconciliation task. Shows AI-driven workflow orchestration.

Unlike the Burr DAG approach (deterministic state machine), this agent:
  • Makes dynamic decisions about tool calling sequence
  • Adapts to unexpected data patterns
  • Provides natural language reasoning for exceptions
  • Demonstrates multi-agent coordination
"""

import json
from anthropic import Anthropic
from typing import Literal

# Initialize Anthropic client
client = Anthropic()


# ── Tool Definitions for Claude ──────────────────────────────────────────

MCP_TOOLS = [
    {
        "name": "get_student_by_kc_id",
        "description": "Look up a student in the brightwheel system using their KinderConnect ID. Returns student profile including brightwheel_id, name, and enrollment details.",
        "input_schema": {
            "type": "object",
            "properties": {
                "kc_id": {
                    "type": "string",
                    "description": "The KinderConnect ID (9-digit string)"
                }
            },
            "required": ["kc_id"]
        }
    },
    {
        "name": "get_student_by_name",
        "description": "Look up a student in the brightwheel system by name. Uses fuzzy matching to handle slight spelling variations. Returns student profile.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "The student's full name"
                }
            },
            "required": ["name"]
        }
    },
    {
        "name": "get_attendance_record",
        "description": "Get a specific student's attendance record for a given date. Returns check-in/check-out times, present status, and signature status.",
        "input_schema": {
            "type": "object",
            "properties": {
                "student_id": {
                    "type": "string",
                    "description": "The brightwheel student ID"
                },
                "date": {
                    "type": "string",
                    "description": "Date in YYYY-MM-DD format"
                }
            },
            "required": ["student_id", "date"]
        }
    },
    {
        "name": "get_meal_authorizations",
        "description": "Get a student's meal service authorizations (which meals they're approved for, FRP category, supper authorization). Used for CACFP reconciliation.",
        "input_schema": {
            "type": "object",
            "properties": {
                "student_id": {
                    "type": "string",
                    "description": "The brightwheel student ID"
                }
            },
            "required": ["student_id"]
        }
    },
    {
        "name": "get_open_invoices",
        "description": "Get all open invoices for a student. Returns balance, due date, and line items. Used for financial reconciliation.",
        "input_schema": {
            "type": "object",
            "properties": {
                "student_id": {
                    "type": "string",
                    "description": "The brightwheel student ID"
                }
            },
            "required": ["student_id"]
        }
    },
    {
        "name": "log_reconciliation_result",
        "description": "Log a reconciliation result to the audit trail. Always use dry_run=True in demo mode.",
        "input_schema": {
            "type": "object",
            "properties": {
                "student_id": {
                    "type": "string",
                    "description": "The brightwheel student ID"
                },
                "workflow": {
                    "type": "string",
                    "description": "Which workflow: 'kinderconnect', 'cacfp', or 'roster'"
                },
                "result": {
                    "type": "string",
                    "description": "Overall result: 'MATCH', 'EXCEPTION', 'VALID', 'NON_PAYABLE', etc."
                },
                "details": {
                    "type": "object",
                    "description": "Detailed reconciliation data"
                },
                "dry_run": {
                    "type": "boolean",
                    "description": "Set to true for demo mode (no writes)"
                }
            },
            "required": ["student_id", "workflow", "result", "details", "dry_run"]
        }
    },
    {
        "name": "get_agency_summary",
        "description": "Get summary statistics for a specific state agency (total authorized students, payment status). Useful for high-level reporting.",
        "input_schema": {
            "type": "object",
            "properties": {
                "agency_name": {
                    "type": "string",
                    "description": "Agency name like 'KinderConnect' or 'CACFP'"
                }
            },
            "required": ["agency_name"]
        }
    }
]


# ── MCP Client Integration ───────────────────────────────────────────────

async def execute_mcp_tool(tool_name: str, tool_input: dict) -> dict:
    """
    Execute an MCP tool call by delegating to the MCP server.

    In production, this would call the remote SSE MCP server.
    For demo, we call the local stdio server.
    """
    from ..workflows.mcp_client import call_mcp_tool
    return await call_mcp_tool(tool_name, tool_input)


# ── Orchestrator Agent ────────────────────────────────────────────────────

async def orchestrate_reconciliation(
    workflow: Literal["kinderconnect", "cacfp", "roster"],
    extracted_records: list[dict],
    max_turns: int = 20
) -> dict:
    """
    Agentic orchestrator using Claude Router Pattern.

    Claude decides:
      • Which tools to call
      • In what sequence
      • How to interpret results
      • When reconciliation is complete
      • Natural language exception reasons

    Args:
        workflow: Which reconciliation workflow
        extracted_records: Records extracted from PDFs/CSVs
        max_turns: Maximum conversation turns (safety limit)

    Returns:
        Reconciliation results in workflow-specific format
    """

    # Build the initial prompt based on workflow type
    if workflow == "kinderconnect":
        system_prompt = """You are a subsidy reconciliation specialist for childcare billing.

Your task: Reconcile KinderConnect attendance records against brightwheel's system of record.

For each record:
1. Look up the student using their kc_id (get_student_by_kc_id)
2. For each day, get their attendance record (get_attendance_record)
3. Compare the records and classify:
   - MATCH: Times within 10 minutes, statuses align
   - TIME_MISMATCH: Times differ by 10+ minutes
   - EXPIRED_AUTH: KC shows "OD" but brightwheel has check-in
   - MISSING_SIGNATURE: Absence without proper documentation
   - ATTENDANCE_MISMATCH: Present/absent status differs
4. Log the result (log_reconciliation_result with dry_run=True)

Provide clear, actionable exception reasons for human operators.

Return results in this JSON format:
{
  "matched": [{"child_name": "...", "kc_id": "...", "overall": "MATCH", "daily_results": [...]}],
  "exceptions": [{"child_name": "...", "kc_id": "...", "overall": "EXCEPTION", "exceptions": [...]}],
  "summary": {"total": N, "matched": M, "exceptions": E, "match_rate": X, "time_saved_hours": 3.5}
}"""
        user_message = f"Reconcile these KinderConnect attendance records:\n\n{json.dumps(extracted_records, indent=2)}"

    elif workflow == "cacfp":
        system_prompt = """You are a CACFP meal service reconciliation specialist.

Your task: Validate meal service records against brightwheel authorizations.

For each record:
1. Look up the student by name (get_student_by_name) - use fuzzy matching
2. Get their meal authorizations (get_meal_authorizations)
3. For each day, validate meals claimed:
   - Check for duplicate meal types (e.g., two PM snacks)
   - Verify supper (S) is authorized
   - Ensure meal count ≤ 5 per day
   - Confirm each meal type is in authorized_meals list
4. Classify as VALID or NON_PAYABLE
5. Log the result (log_reconciliation_result with dry_run=True)

Meal codes: B=breakfast, AM=am_snack, L=lunch, P=pm_snack, S=supper, E=evening_snack

Return results in this JSON format:
{
  "valid": [{"child_name": "...", "frp_category": "...", "overall": "VALID", "daily_results": [...]}],
  "non_payable": [{"child_name": "...", "frp_category": "...", "overall": "NON_PAYABLE", "non_payable": [...]}],
  "summary": {"total": N, "valid": V, "non_payable": NP, "valid_rate": X, "time_saved_hours": 2.5}
}"""
        user_message = f"Validate these CACFP meal records:\n\n{json.dumps(extracted_records, indent=2)}"

    else:  # roster
        system_prompt = """You are an enrollment roster data normalization specialist.

Your task: Normalize messy roster data for upload to brightwheel.

For each record:
1. Look up if student already exists (get_student_by_name)
2. Validate required fields (name, status, homeroom, parent contact)
3. Flag issues:
   - Missing required fields
   - Invalid status values
   - Duplicate records
   - Formatting problems
4. Classify as "ready_to_upload" or "flagged"

Return results in this JSON format:
{
  "ready": [{"name": "...", "status": "...", "homeroom": "...", "ready_to_upload": true, ...}],
  "flagged": [{"name": "...", "issues": ["..."], "ready_to_upload": false, ...}],
  "summary": {"total": N, "ready": R, "flagged": F, "time_saved_hours": 1.0}
}"""
        user_message = f"Normalize this enrollment roster:\n\n{json.dumps(extracted_records, indent=2)}"

    # Initialize conversation
    messages = [{"role": "user", "content": user_message}]

    # Multi-turn agentic loop
    for turn in range(max_turns):
        # Call Claude with tool calling enabled
        response = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=8192,
            system=system_prompt,
            tools=MCP_TOOLS,
            messages=messages
        )

        # Check if Claude is done (no more tool calls)
        if response.stop_reason == "end_turn":
            # Extract final JSON response
            final_text = ""
            for block in response.content:
                if block.type == "text":
                    final_text += block.text

            # Parse JSON result
            try:
                # Find JSON in the response (may have surrounding text)
                json_start = final_text.find("{")
                json_end = final_text.rfind("}") + 1
                if json_start != -1 and json_end > json_start:
                    result = json.loads(final_text[json_start:json_end])
                    return result
                else:
                    # Fallback: return text response
                    return {"error": "Could not parse JSON from response", "raw_response": final_text}
            except json.JSONDecodeError as e:
                return {"error": f"JSON decode error: {e}", "raw_response": final_text}

        # Process tool calls
        if response.stop_reason == "tool_use":
            # Add assistant's response to conversation
            messages.append({"role": "assistant", "content": response.content})

            # Execute each tool call
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    tool_name = block.name
                    tool_input = block.input

                    # Execute via MCP
                    try:
                        result = await execute_mcp_tool(tool_name, tool_input)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(result)
                        })
                    except Exception as e:
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps({"error": str(e)}),
                            "is_error": True
                        })

            # Add tool results to conversation
            messages.append({"role": "user", "content": tool_results})

        else:
            # Unexpected stop reason
            return {"error": f"Unexpected stop reason: {response.stop_reason}"}

    # Hit max turns
    return {"error": f"Reached maximum turns ({max_turns}) without completion"}


# ── Parallel Processing ───────────────────────────────────────────────────

async def run_agentic_reconciliation(
    workflow: Literal["kinderconnect", "cacfp", "roster"],
    extracted_records: list[dict]
) -> dict:
    """
    Run agentic reconciliation for all records.

    Note: For interview demo, we do a single agent call with all records.
    In production, you might batch records or run parallel agent instances.
    """
    return await orchestrate_reconciliation(workflow, extracted_records)
