import asyncio
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.agents.hybrid_orchestrator import _synthesise_batch, ReconciliationRecord, StudentPlan

def test_imports():
    print("Imports successful.")
    
    # Simple syntax check
    r = ReconciliationRecord(child_name="Test", kc_id="123")
    print(f"Record created: {r.child_name}, found={r.found}")

if __name__ == "__main__":
    test_imports()
