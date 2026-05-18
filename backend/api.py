"""
FastAPI Backend for Subsidy Reconciliation Frontend

Connects React frontend → Python pipeline (real orchestrator)
"""

from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import asyncio
import json
import uuid
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime
import sys
from dotenv import load_dotenv

# Load environment variables for Jira credentials
load_dotenv()

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from src.agents.extraction_agent import extract
from src.agents.grader_agent import grade
# HYBRID: Claude decides + Burr batches execution
from src.agents.hybrid_orchestrator import hybrid_reconcile
from src.agents.exception_handler import handle_exceptions
from src.workflows.mcp_pool import initialize_mcp_pool, shutdown_mcp_pool

app = FastAPI(title="Brightwheel Subsidy Reconciliation API")

# Startup/Shutdown events for MCP connection pool
@app.on_event("startup")
async def startup_event():
    """Initialize MCP connection pool at startup."""
    print("[Backend] Initializing MCP connection pool...")
    await initialize_mcp_pool()
    print("[Backend] MCP pool ready!")

@app.on_event("shutdown")
async def shutdown_event():
    """Shutdown MCP connection pool."""
    print("[Backend] Shutting down MCP pool...")
    await shutdown_mcp_pool()

# CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory job storage (production: Redis/PostgreSQL)
jobs: Dict[str, Dict] = {}

# Organize uploads by timestamp
BASE_UPLOAD_DIR = Path("uploads")
BASE_UPLOAD_DIR.mkdir(exist_ok=True)


@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...), workflow: str = "kinderconnect"):
    """Upload a subsidy report file."""
    try:
        # Create timestamp-based folder for this upload session
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        upload_dir = BASE_UPLOAD_DIR / timestamp
        upload_dir.mkdir(exist_ok=True)

        # Save file
        file_id = str(uuid.uuid4())
        file_path = upload_dir / f"{workflow}_{file.filename}"

        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)

        return {
            "file_id": file_id,
            "filename": file.filename,
            "workflow": workflow,
            "path": str(file_path),
            "session": timestamp
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/reconcile")
async def start_reconciliation(background_tasks: BackgroundTasks, files: Dict[str, str]):
    """
    Start reconciliation process.

    Body: {
        "kinderconnect": "file_id",
        "cacfp": "file_id",
        "roster": "file_id"
    }
    """
    job_id = str(uuid.uuid4())

    # Initialize job
    jobs[job_id] = {
        "status": "queued",
        "progress": 0,
        "stage": "initializing",
        "message": "Job queued",
        "results": None,
        "error": None,
        "tool_calls": []  # Track every tool call
    }

    # Run in background
    background_tasks.add_task(run_reconciliation, job_id, files)

    return {"job_id": job_id}


async def run_reconciliation(job_id: str, files: Dict[str, str]):
    """Background task that runs the actual reconciliation."""
    print(f"[DEBUG] Starting reconciliation job {job_id}")
    print(f"[DEBUG] Files: {files}")

    def add_tool_call(tool_type, tool_name, state, input_data=None, output_data=None):
        """Add a tool call to the tracking list."""
        tool_call = {
            "type": tool_type,  # "claude_api" or "mcp_tool"
            "name": tool_name,
            "state": state,  # "pending", "running", "completed", "failed"
            "input": input_data,
            "output": output_data,
            "timestamp": datetime.now().isoformat()
        }
        jobs[job_id]["tool_calls"].append(tool_call)
        return len(jobs[job_id]["tool_calls"]) - 1  # Return index

    def update_tool_call(index, state, output_data=None):
        """Update a tool call's state and output."""
        if index < len(jobs[job_id]["tool_calls"]):
            jobs[job_id]["tool_calls"][index]["state"] = state
            if output_data:
                jobs[job_id]["tool_calls"][index]["output"] = output_data

    def update_progress(stage, message, api_calls_done, total_api_calls):
        """Update progress based on actual API calls completed."""
        percent = int((api_calls_done / total_api_calls) * 100) if total_api_calls > 0 else 0
        jobs[job_id]["status"] = "running"
        jobs[job_id]["stage"] = stage
        jobs[job_id]["message"] = message
        jobs[job_id]["progress"] = percent
        jobs[job_id]["api_calls"] = {"done": api_calls_done, "total": total_api_calls}
        print(f"[PROGRESS] {message} ({api_calls_done}/{total_api_calls} API calls = {percent}%)")

    try:
        workflows = []
        extracted = {}
        total_api_calls = 0
        api_calls_done = 0

        # Step 1: Extraction
        for workflow_type, file_id in files.items():
            if not file_id:
                continue

            # Find the uploaded file (search all timestamp folders)
            # Get most recent upload directory and find file containing workflow name
            file_path = None
            timestamp_dirs = sorted([d for d in BASE_UPLOAD_DIR.iterdir() if d.is_dir()], reverse=True)

            if timestamp_dirs:
                latest_dir = timestamp_dirs[0]
                # Just find any file containing the workflow name
                all_files = list(latest_dir.glob("*"))
                matches = [f for f in all_files if workflow_type in f.name.lower()]
                if matches:
                    file_path = matches[0]
                    print(f"[UPLOAD] Found {workflow_type} file: {file_path.name}")

            if not file_path:
                print(f"[WARNING] File not found for {workflow_type}")
                continue
            workflows.append(workflow_type)
            total_api_calls += 1  # Extraction API call

            # Track Claude API call for extraction
            tool_idx = add_tool_call(
                tool_type="claude_api",
                tool_name=f"extract_{workflow_type}",
                state="running",
                input_data={"file": file_path.name, "workflow": workflow_type}
            )
            update_progress("extraction", f"Claude API: Extracting {workflow_type}...", api_calls_done, total_api_calls)

            extracted[workflow_type] = await extract(str(file_path), workflow=workflow_type)

            update_tool_call(tool_idx, "completed", {"records_extracted": len(extracted[workflow_type])})
            api_calls_done += 1

            update_progress("extraction", f"Extracted {len(extracted[workflow_type])} records from {workflow_type}", api_calls_done, total_api_calls)

        if not workflows:
            raise Exception("No files provided for reconciliation")

        # Calculate total API calls needed for reconciliation
        for workflow in workflows:
            # Planning call + batch execution + synthesis + grading
            total_api_calls += 4

        # Step 2: Reconciliation (HYBRID: Claude decides + batched execution)
        results = {}
        for workflow in workflows:
            # Planning
            plan_idx = add_tool_call(
                tool_type="claude_api",
                tool_name=f"plan_{workflow}",
                state="running",
                input_data={"workflow": workflow, "records": len(extracted[workflow])}
            )
            update_progress("reconciliation", f"Claude API: Planning {workflow} strategy...", api_calls_done, total_api_calls)

            # Batch execution (track as single batched call)
            batch_idx = add_tool_call(
                tool_type="mcp_batch",
                tool_name=f"batch_reconcile_{workflow}",
                state="running",
                input_data={"workflow": workflow, "students": len(extracted[workflow])}
            )
            update_progress("reconciliation", f"MCP Batch: Parallel tool calls for {workflow}...", api_calls_done, total_api_calls)

            result = await hybrid_reconcile(workflow, extracted[workflow])
            results[workflow] = result

            update_tool_call(plan_idx, "completed", {"strategy": "batch_all"})
            api_calls_done += 1

            update_tool_call(batch_idx, "completed", {
                "lookups": len(extracted[workflow]),
                "attendance_checks": len(extracted[workflow]) * 5,
                "matched": result.get("summary", {}).get("matched_children", 0),
                "exceptions": result.get("summary", {}).get("exception_children", 0)
            })
            api_calls_done += 1

            # Synthesis
            synth_idx = add_tool_call(
                tool_type="claude_api",
                tool_name=f"synthesize_{workflow}",
                state="running",
                input_data={"workflow": workflow}
            )
            update_progress("reconciliation", f"Claude API: Synthesizing {workflow} results...", api_calls_done, total_api_calls)
            update_tool_call(synth_idx, "completed", result.get("summary", {}))
            api_calls_done += 1

            # Exception Handling: Auto-create Jira tickets for HIGH/CRITICAL exceptions
            if result.get("exceptions") and len(result["exceptions"]) > 0:
                jira_idx = add_tool_call(
                    tool_type="jira_api",
                    tool_name="create_jira_tickets",
                    state="running",
                    input_data={
                        "workflow": workflow,
                        "exceptions": len(result["exceptions"]),
                        "high_critical": len([e for e in result["exceptions"] if e.get("severity") in ["HIGH", "CRITICAL"]])
                    }
                )
                update_progress("reconciliation", f"Jira API: Creating tickets for {workflow} exceptions...", api_calls_done, total_api_calls)

                jira_result = handle_exceptions(
                    workflow=workflow,
                    exceptions=result["exceptions"],
                    auto_create_tickets=True
                )

                # Attach Jira tickets to result
                result["jira_tickets"] = jira_result["tickets_created"]
                result["jira_summary"] = jira_result["summary"]

                update_tool_call(jira_idx, "completed", {
                    "tickets_created": len(jira_result["tickets_created"]),
                    "tickets": [{"key": t["issue_key"], "url": t["url"]} for t in jira_result["tickets_created"]]
                })
                api_calls_done += 1
                total_api_calls += 1  # Add to total since we discovered exceptions

        # Step 3: Grading
        grades = {}
        for workflow in workflows:
            update_progress("grading", f"Claude API: Grading {workflow} quality...", api_calls_done, total_api_calls)
            grade_result = await grade(workflow, extracted[workflow], results[workflow])
            grades[workflow] = grade_result
            api_calls_done += 1

        # Complete
        update_progress("complete", "Reconciliation complete!", api_calls_done, total_api_calls)
        jobs[job_id]["status"] = "complete"
        final_results = {
            "workflows": workflows,
            "extracted": extracted,
            "results": results,
            "grades": grades,
            "job_id": job_id,
            "completed_at": datetime.now().isoformat()
        }
        jobs[job_id]["results"] = final_results

        # Save results to the session folder
        if file_path and file_path.parent.exists():
            results_file = file_path.parent / "results.json"
            with open(results_file, "w") as f:
                json.dump(final_results, f, indent=2)
            print(f"[Job {job_id}] Results saved to {results_file}")

    except Exception as e:
        print(f"[ERROR] Job {job_id} failed: {str(e)}")
        import traceback
        traceback.print_exc()
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["error"] = str(e)
        jobs[job_id]["message"] = f"Error: {str(e)}"


@app.get("/api/job/{job_id}")
async def get_job_status(job_id: str):
    """Get job status and results."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    return jobs[job_id]


@app.get("/api/job/{job_id}/stream")
async def stream_job_status(job_id: str):
    """Stream job progress via Server-Sent Events."""
    async def event_generator():
        while True:
            if job_id not in jobs:
                yield f"data: {json.dumps({'error': 'Job not found'})}\n\n"
                break

            job = jobs[job_id]
            yield f"data: {json.dumps(job)}\n\n"

            if job["status"] in ["complete", "failed"]:
                break

            await asyncio.sleep(1)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "brightwheel-subsidy-reconciliation"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
