"""
Rich Terminal Report

Three tables, one per workflow, with color-coded status.
"""

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text


console = Console()


def print_report(workflows: list[str], extracted: dict, results: dict, grades: dict):
    """Print rich colored terminal report."""

    # ── KinderConnect Report ──────────────────────────────────────────────
    if "kinderconnect" in workflows and "kinderconnect" in results:
        kc_result = results["kinderconnect"]

        table = Table(title="KinderConnect Attendance Reconciliation", show_header=True)
        table.add_column("Child", style="cyan")
        table.add_column("KC ID", style="dim")
        table.add_column("Mon", justify="center")
        table.add_column("Tue", justify="center")
        table.add_column("Wed", justify="center")
        table.add_column("Thu", justify="center")
        table.add_column("Fri", justify="center")
        table.add_column("Status", justify="center")

        all_records = kc_result.get("matched", []) + kc_result.get("exceptions", [])

        for record in all_records:
            # Get daily statuses
            days = ["2026-05-05", "2026-05-06", "2026-05-07", "2026-05-08", "2026-05-09"]
            day_statuses = []

            for date in days:
                day_result = next((d for d in record.get("daily_results", []) if d["date"] == date), None)
                if day_result:
                    # Handle both Burr format (classification) and agentic format (status)
                    classification = day_result.get("classification") or day_result.get("status")
                    if classification == "MATCH":
                        day_statuses.append("[green]OK[/green]")
                    elif classification == "TIME_MISMATCH":
                        day_statuses.append("[yellow]![/yellow]")
                    elif classification == "EXPIRED_AUTH":
                        day_statuses.append("[red]X[/red]")
                    elif classification == "MISSING_SIGNATURE":
                        day_statuses.append("[yellow]S[/yellow]")
                    else:
                        day_statuses.append("[red]?[/red]")
                else:
                    day_statuses.append("[dim]-[/dim]")

            # Overall status
            if record["overall"] == "MATCH":
                overall = "[green]MATCH[/green]"
            elif record["overall"] == "NOT_FOUND":
                overall = "[red]NOT FOUND[/red]"
            else:
                overall = "[yellow]EXCEPTION[/yellow]"

            table.add_row(
                record["child_name"],
                record["kc_id"],
                *day_statuses,
                overall
            )

        console.print(table)
        console.print()

        # Show exception details
        if kc_result.get("exceptions"):
            console.print("[yellow]Exception Details:[/yellow]")
            for exc in kc_result["exceptions"][:3]:  # Show first 3
                # Agentic format has action_required and recommended_next_steps
                if exc.get("action_required"):
                    console.print(f"  • {exc['child_name']}: {exc['action_required']}")
                elif exc.get("exceptions"):
                    for ex in exc["exceptions"]:
                        console.print(f"  • {exc['child_name']}: {ex.get('reason', 'Unknown issue')}")
            console.print()

    # ── CACFP Report ──────────────────────────────────────────────────────
    if "cacfp" in workflows and "cacfp" in results:
        cacfp_result = results["cacfp"]

        table = Table(title="CACFP Meal Count Validation", show_header=True)
        table.add_column("Child", style="cyan")
        table.add_column("FRP", justify="center")
        table.add_column("Mon", justify="center")
        table.add_column("Tue", justify="center")
        table.add_column("Wed", justify="center")
        table.add_column("Thu", justify="center")
        table.add_column("Fri", justify="center")
        table.add_column("Status", justify="center")

        all_records = cacfp_result["valid"] + cacfp_result["non_payable"]

        for record in all_records:
            # Get daily meal counts
            days = ["2026-05-05", "2026-05-06", "2026-05-07", "2026-05-08", "2026-05-09"]
            day_meals = []

            for date in days:
                day_result = next((d for d in record.get("daily_results", []) if d["date"] == date), None)
                if day_result:
                    meal_count = len(day_result.get("meals", []))
                    if day_result["classification"] == "VALID":
                        day_meals.append(f"[green]{meal_count}[/green]")
                    else:
                        day_meals.append(f"[red]{meal_count}[/red]")
                else:
                    day_meals.append("[dim]-[/dim]")

            # Overall status
            if record["overall"] == "VALID":
                overall = "[green]VALID[/green]"
            elif record["overall"] == "NOT_FOUND":
                overall = "[red]NOT FOUND[/red]"
            else:
                overall = "[red]NON-PAYABLE[/red]"

            frp = record.get("frp_category", "?")[:1].upper()  # F/R/P

            table.add_row(
                record["child_name"],
                frp,
                *day_meals,
                overall
            )

        console.print(table)
        console.print()

        # Show non-payable details
        if cacfp_result["non_payable"]:
            console.print("[red]Non-Payable Issues:[/red]")
            for exc in cacfp_result["non_payable"][:3]:
                if exc.get("non_payable"):
                    for ex in exc["non_payable"]:
                        console.print(f"  • {exc['child_name']}: {ex.get('reason', 'Unknown issue')}")
            console.print()

    # ── Roster Report ─────────────────────────────────────────────────────
    if "roster" in workflows and "roster" in results:
        roster_result = results["roster"]

        table = Table(title="Enrollment Roster Normalization", show_header=True)
        table.add_column("Name", style="cyan")
        table.add_column("Status")
        table.add_column("Homeroom")
        table.add_column("Contact")
        table.add_column("Issues", style="yellow")
        table.add_column("Ready?", justify="center")

        all_records = roster_result["ready"] + roster_result["flagged"]

        for record in all_records:
            contact = record.get("parent_email") or record.get("parent_phone") or "[dim]None[/dim]"
            issues = ", ".join(record.get("issues", []))[:40] if record.get("issues") else ""

            ready = "[green]OK[/green]" if record["ready_to_upload"] else "[red]X[/red]"

            table.add_row(
                record["name"],
                record.get("status", "[dim]?[/dim]"),
                record.get("homeroom", "[dim]?[/dim]"),
                contact,
                issues,
                ready
            )

        console.print(table)
        console.print()

    # ── Summary Panel ─────────────────────────────────────────────────────
    summary_lines = ["[bold]brightwheel Reconciliation — Week of May 5-9, 2026[/bold]", ""]

    for wf in workflows:
        if wf not in results:
            continue

        result = results[wf]
        grade = grades.get(wf, {})
        summary = result["summary"]

        if wf == "kinderconnect":
            matched = summary.get('matched', summary.get('matched_children', 0))
            exceptions = summary.get('exceptions', summary.get('exception_children', 0))
            summary_lines.append(
                f"KinderConnect: {matched} matched, {exceptions} exceptions "
                f"(Grader: {grade.get('score', '?')}/10)"
            )
        elif wf == "cacfp":
            summary_lines.append(
                f"CACFP: {summary['valid']} valid, {summary['non_payable']} non-payable "
                f"(Grader: {grade.get('score', '?')}/10)"
            )
        elif wf == "roster":
            summary_lines.append(
                f"Roster: {summary['ready']} ready, {summary['flagged']} flagged "
                f"(Grader: {grade.get('score', '?')}/10)"
            )

    total_time = sum(results[wf]["summary"].get("time_saved_hours", 0) for wf in results.keys())
    summary_lines.append("")
    summary_lines.append(f"[green]Time saved: ~{total_time:.1f} hours → ~10 minutes (98% reduction)[/green]")

    console.print(Panel("\n".join(summary_lines), border_style="green"))
