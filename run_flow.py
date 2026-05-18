import asyncio
import json
import sys
import os

from src.agents.extraction_agent import extract
from src.agents.hybrid_orchestrator import hybrid_reconcile
from src.workflows.mcp_pool import initialize_mcp_pool, shutdown_mcp_pool

async def run_flow():
    await initialize_mcp_pool()
    try:
        results = {}
        
        # Run KinderConnect
        kc_file = "data/kinderconnect_report.pdf"
        print(f"Extracting from {kc_file}...")
        kc_records = await extract(kc_file)
        print(f"Extracted {len(kc_records)} KinderConnect records.")
        
        print("Reconciling KinderConnect...")
        kc_result = await hybrid_reconcile("kinderconnect", kc_records)
        results["kinderconnect"] = kc_result
        
        # Run CACFP
        cacfp_file = "data/cacfp_meal_count.pdf"
        print(f"Extracting from {cacfp_file}...")
        cacfp_records = await extract(cacfp_file)
        print(f"Extracted {len(cacfp_records)} CACFP records.")
        
        print("Reconciling CACFP...")
        cacfp_result = await hybrid_reconcile("cacfp", cacfp_records)
        results["cacfp"] = cacfp_result
        
        # Save results
        with open("new_results.json", "w") as f:
            json.dump(results, f, indent=2)
        print("Saved to new_results.json")
    finally:
        await shutdown_mcp_pool()

if __name__ == "__main__":
    asyncio.run(run_flow())
