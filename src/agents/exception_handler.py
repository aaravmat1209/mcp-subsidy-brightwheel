"""
Exception Handler Agent - Auto-creates Jira tickets for subsidy exceptions

Uses atlassian-python-api to automatically create Jira issues
when reconciliation exceptions are found.

Architecture:
1. Receives exceptions from reconciliation
2. For each critical exception:
   - Creates Jira ticket via Jira API
   - Assigns priority based on severity
3. Returns ticket IDs for tracking
"""

import os
from atlassian import Jira


def create_jira_ticket_for_exception(exception: dict, workflow: str, jira_client: Jira) -> dict:
    """
    Create a Jira ticket for a reconciliation exception.

    Args:
        exception: Exception data from reconciliation
        workflow: Workflow type (kinderconnect, cacfp, roster)
        jira_client: Initialized Jira client

    Returns:
        Jira ticket details (issue_key, url)
    """
    severity = exception.get("severity", exception.get("exception_type", "MEDIUM"))
    child_name = exception.get("child_name", "Unknown")

    # Build ticket summary
    summary = f"Subsidy Exception: {child_name} - {workflow.upper()}"

    # Extract description from exception
    if "action_required" in exception:
        description = exception["action_required"]
    elif "exceptions" in exception and len(exception["exceptions"]) > 0:
        description = exception["exceptions"][0].get("reason", "Exception found during reconciliation")
    else:
        description = "Exception found during subsidy reconciliation"

    # Fix for MISSING_STUDENT: clarify which system has the record
    if exception.get("exception_type") == "MISSING_STUDENT" or "not found in brightwheel" in description.lower():
        description = f"Student found in KinderConnect but not in Brightwheel. Verify enrollment status and ensure student records are synchronized."

    # Add detailed info
    description += f"\n\nWorkflow: {workflow}\n"
    description += f"Severity: {severity}\n"
    description += f"Student: {child_name}\n"

    if "kc_id" in exception:
        description += f"KinderConnect ID: {exception['kc_id']}\n"

    if "exceptions" in exception:
        description += "\nDetails:\n"
        for exc in exception["exceptions"][:3]:  # First 3 issues
            description += f"- {exc.get('date', 'N/A')}: {exc.get('reason', exc.get('issue', 'Unknown'))}\n"

    description += "\nThis ticket was automatically created by the brightwheel subsidy reconciliation system."

    # Map severity to Jira priority
    priority_map = {
        "CRITICAL": "Highest",
        "HIGH": "High",
        "MEDIUM": "Medium",
        "LOW": "Low"
    }
    jira_priority = priority_map.get(severity, "Medium")

    # Create Jira issue
    issue = jira_client.issue_create(
        fields={
            "project": {"key": "KAN"},
            "summary": summary,
            "description": description,
            "issuetype": {"name": "Task"},
            "priority": {"name": jira_priority}
        }
    )

    jira_url = os.getenv("ATLASSIAN_JIRA_URL", "")

    return {
        "issue_key": issue["key"],
        "url": f"{jira_url}/browse/{issue['key']}",
        "summary": summary,
        "description": description,
        "status": "To Do"
    }


def handle_exceptions(
    workflow: str,
    exceptions: list[dict],
    auto_create_tickets: bool = True
) -> dict:
    """
    Handle all exceptions from reconciliation.

    Args:
        workflow: Workflow type
        exceptions: List of exceptions
        auto_create_tickets: Whether to auto-create Jira tickets

    Returns:
        {
            "tickets_created": [...],
            "summary": {...}
        }
    """

    tickets_created = []

    if auto_create_tickets:
        # Initialize Jira client
        jira_url = os.getenv("ATLASSIAN_JIRA_URL", "")
        jira_email = os.getenv("ATLASSIAN_JIRA_EMAIL", "")
        jira_token = os.getenv("ATLASSIAN_JIRA_TOKEN")

        if not jira_token:
            print("Warning: ATLASSIAN_JIRA_TOKEN not set, skipping Jira ticket creation")
            return {
                "tickets_created": [],
                "summary": {
                    "total_exceptions": len(exceptions),
                    "tickets_created": 0,
                    "auto_ticketing_enabled": False,
                    "error": "Jira credentials not configured"
                }
            }

        jira = Jira(
            url=jira_url,
            username=jira_email,
            password=jira_token,
            cloud=True
        )

        for exception in exceptions:
            # Only create tickets for HIGH/CRITICAL severity
            severity = exception.get("severity", exception.get("exception_type", "MEDIUM"))
            if severity in ["CRITICAL", "HIGH"]:
                ticket = create_jira_ticket_for_exception(exception, workflow, jira)
                tickets_created.append(ticket)

    return {
        "tickets_created": tickets_created,
        "summary": {
            "total_exceptions": len(exceptions),
            "tickets_created": len(tickets_created),
            "auto_ticketing_enabled": auto_create_tickets
        }
    }


# Removed MCP approach - now using direct atlassian-python-api integration
