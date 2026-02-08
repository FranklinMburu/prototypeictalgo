"""
runner.py: Entrypoint for orchestrating decision persistence and notification.
- Loads a sample decision from sample_xauusd.json
- Initializes the orchestrator
- Persists and notifies
- Prints results and closes resources
"""
import asyncio
import json
import os
from reasoner_service.orchestrator import DecisionOrchestrator
from reasoner_service.logging_setup import logger

SAMPLE_PATH = os.path.join(os.path.dirname(__file__), "sample_xauusd.json")

def load_sample_decision():
    with open(SAMPLE_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    # Map sample fields to orchestrator expected fields
    decision = {
        "symbol": data.get("symbol", "UNKNOWN"),
        "confidence": data.get("alignment_score", 0.0),
        "bias": data["tfs"][0]["bias_local"] if data.get("tfs") else "neutral",
        "recommendation": "enter",  # Example, adapt as needed
        "summary": f"Volatility: {data.get('analytics',{}).get('volatility_index','N/A')}, Accel_M5: {data.get('analytics',{}).get('accel_M5','N/A')}",
        "duration_ms": 0,
        "timestamp_ms": data.get("snapshot_ts"),
        "raw": data,
    }
    return decision

async def main():
    logger.info("Starting orchestration demo...")
    orch = DecisionOrchestrator()
    await orch.setup()
    decision = load_sample_decision()
    logger.info(f"Loaded sample decision: {decision}")
    result = await orch.process_decision(decision, persist=True)
    print("Orchestration result:\n", json.dumps(result, indent=2))
    await orch.close()
    logger.info("Orchestration complete.")

if __name__ == "__main__":
    asyncio.run(main())
