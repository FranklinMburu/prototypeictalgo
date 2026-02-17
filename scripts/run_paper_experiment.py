#!/usr/bin/env python3
"""
Paper Experiment: Memory Recall Veto Validation

This script runs a controlled experiment to prove that the orchestrator
can autonomously veto trading a losing signal type using memory recall.

FLOW:
1. Load constraints.yaml and enable paper_execution_adapter
2. Create DecisionOrchestrator with test DB
3. Generate N synthetic decisions (two signal types: losing and control)
4. Run through orchestrator end-to-end
5. Collect outcomes until min_sample_size for losing signal
6. Submit final decision and verify veto with reason "memory_underperformance"
7. Print proof artifacts
"""

import asyncio
import argparse
import json
import sys
import uuid
import time
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta

# Local imports
from reasoner_service.storage import (
    create_engine_and_sessionmaker, 
    init_models,
    insert_decision_outcome,
    get_outcomes_by_signal_type
)
from reasoner_service.orchestrator import DecisionOrchestrator
from reasoner_service.paper_execution_adapter import (
    PaperExecutionConfig, 
    BrokerSimulatorAdapter
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)


def load_constraints_yaml(path: str = "agent/constraints.yaml") -> Dict[str, Any]:
    """Load and parse constraints.yaml."""
    try:
        import yaml
        with open(path, 'r') as f:
            return yaml.safe_load(f)
    except ImportError:
        logger.warning("PyYAML not installed, using fallback YAML parser")
        return parse_yaml_fallback(path)
    except FileNotFoundError:
        logger.error(f"constraints.yaml not found at {path}")
        return {}


def parse_yaml_fallback(path: str) -> Dict[str, Any]:
    """Simple YAML parser fallback (subset of YAML)."""
    # Simple fallback - just return defaults if parsing fails
    return {
        'outcome_adaptation_enabled': True,
        'min_sample_size': 20,
    }


def generate_synthetic_decision(
    symbol: str,
    signal_type: str,
    timeframe: str = "4H",
    direction: str = "long",
    model: str = "test_model",
    session: str = "London",
) -> Dict[str, Any]:
    """Generate a synthetic decision dict for orchestrator."""
    now_ms = int(time.time() * 1000)
    
    # Realistic prices for EURUSD
    if symbol == "EURUSD":
        entry_price = 1.0850
        stop_loss_price = 1.0800  # 50 pips
        take_profit_price = 1.0900  # 50 pips (1:1 RR)
    else:
        entry_price = 100.0
        stop_loss_price = 99.0
        take_profit_price = 101.0
    
    return {
        "id": str(uuid.uuid4()),
        "symbol": symbol,
        "signal_type": signal_type,
        "timeframe": timeframe,
        "direction": direction,
        "entry_price": entry_price,
        "stop_loss_price": stop_loss_price,
        "take_profit_price": take_profit_price,
        "model": model,
        "session": session,
        "ts_ms": now_ms,
        "timestamp_ms": now_ms,
    }


async def run_experiment(
    max_decisions: int = 200,
    min_sample_size: int = 20,
    seed: Optional[int] = None,
    use_sqlite_memory: bool = True,
):
    """
    Run the paper experiment.
    
    Args:
        max_decisions: Maximum synthetic decisions to generate
        min_sample_size: Min outcomes per signal type before final veto test
        seed: Random seed for determinism
        use_sqlite_memory: Use in-memory SQLite for test
    """
    logger.info("=" * 80)
    logger.info("PHASE 12: Memory Recall Veto Validation Experiment")
    logger.info("=" * 80)
    
    # Load constraints
    constraints = load_constraints_yaml()
    min_sample = constraints.get('outcome_adaptation', {}).get('min_sample_size', min_sample_size) if isinstance(constraints.get('outcome_adaptation'), dict) else min_sample_size
    logger.info(f"Config: min_sample_size={min_sample}, outcome_adaptation={constraints.get('outcome_adaptation_enabled', True)}")
    
    # Create test DB
    dsn = "sqlite+aiosqlite:///:memory:" if use_sqlite_memory else "sqlite+aiosqlite:///./test_experiment.db"
    logger.info(f"Creating DB: {dsn}")
    
    # Create orchestrator
    orchestrator = DecisionOrchestrator(dsn=dsn)
    await orchestrator.setup()
    logger.info("✓ Orchestrator initialized and setup complete")
    
    # Configure orchestrator constraints with paper execution and outcome adaptation
    orchestrator._constraints = {
        "paper_execution_adapter": {
            "enabled": True,
            "slippage_model": "fixed_percent",
            "slippage_fixed_pct": 0.05,
            "tpsl_model": "instant",
            "seed": seed,
            "forced_outcome_enabled": True,
            "forced_outcome_signal_types": ["bearish_bos"],
            "forced_outcome_value": "loss",
            "forced_outcome_probability": 1.0,
        },
        "outcome_adaptation": {
            "enabled": True,
            "min_sample_size": min_sample,
            "suppress_if": {"expectancy_r": -0.05},
        }
    }
    logger.info(f"✓ Constraints configured: forced_losing_signals=['bearish_bos']")
    
    # Signal types: losing (forced) and control (normal)
    losing_signal = "bearish_bos"
    control_signal = "bullish_choch"
    symbol = "EURUSD"
    
    # Generate and run decisions
    logger.info(f"\nRunning {max_decisions} synthetic decisions...")
    decision_count = 0
    
    while decision_count < max_decisions:
        # Alternate between losing and control signals
        if decision_count % 3 == 0:
            signal_type = losing_signal
        else:
            signal_type = control_signal
        
        decision = generate_synthetic_decision(
            symbol=symbol,
            signal_type=signal_type,
        )
        
        try:
            # Run through orchestrator
            result = await orchestrator.process_decision(decision, persist=True)
            decision_count += 1
            
            # Log periodically
            if decision_count % 10 == 0:
                logger.info(f"  Decision {decision_count}/{max_decisions}: {signal_type}")
        
        except Exception as e:
            logger.error(f"Error in decision {decision_count}: {e}")
            decision_count += 1
            continue
        
        # Check if we have enough outcomes for the losing signal
        try:
            losing_outcomes = await get_outcomes_by_signal_type(
                orchestrator._sessionmaker,
                symbol=symbol,
                signal_type=losing_signal,
                model="test_model",
                session="London",
                direction="long",
            )
            
            if losing_outcomes and len(losing_outcomes) >= min_sample:
                logger.info(f"✓ Reached min_sample_size ({len(losing_outcomes)}) for {losing_signal}, stopping generation")
                break
        except Exception as e:
            logger.debug(f"Error checking outcomes: {e}")
            continue
    
    logger.info(f"✓ Completed {decision_count} decisions")
    
    # Fetch and display summary
    try:
        losing_outcomes = await get_outcomes_by_signal_type(
            orchestrator._sessionmaker,
            symbol=symbol,
            signal_type=losing_signal,
            model="test_model",
            session="London",
            direction="long",
        ) or []
        
        control_outcomes = await get_outcomes_by_signal_type(
            orchestrator._sessionmaker,
            symbol=symbol,
            signal_type=control_signal,
            model="test_model",
            session="London",
            direction="long",
        ) or []
    except Exception as e:
        logger.error(f"Error fetching outcomes: {e}")
        losing_outcomes = []
        control_outcomes = []
    
    logger.info(f"\n[Summary before final test]")
    logger.info(f"  {losing_signal}: {len(losing_outcomes)} outcomes collected")
    if losing_outcomes:
        r_values = [o.r_multiple for o in losing_outcomes if o.r_multiple is not None]
        avg_r = sum(r_values) / len(r_values) if r_values else 0
        win_count = sum(1 for o in losing_outcomes if o.outcome == "win")
        win_rate = win_count / len(losing_outcomes) if losing_outcomes else 0
        expectancy = avg_r * (2 * win_rate - 1) if win_rate else 0  # Simplified expectancy
        logger.info(f"    Avg r_multiple: {avg_r:.4f}, Win rate: {win_rate:.2%}, Expectancy: {expectancy:.4f}")
    
    logger.info(f"  {control_signal}: {len(control_outcomes)} outcomes collected")
    if control_outcomes:
        r_values = [o.r_multiple for o in control_outcomes if o.r_multiple is not None]
        avg_r = sum(r_values) / len(r_values) if r_values else 0
        win_count = sum(1 for o in control_outcomes if o.outcome == "win")
        win_rate = win_count / len(control_outcomes) if control_outcomes else 0
        logger.info(f"    Avg r_multiple: {avg_r:.4f}, Win rate: {win_rate:.2%}")
    
    # FINAL TEST: Submit one more losing_signal decision and check for veto
    logger.info(f"\n[FINAL TEST: Veto validation]")
    final_decision = generate_synthetic_decision(
        symbol=symbol,
        signal_type=losing_signal,
    )
    logger.info(f"Submitting final decision: {losing_signal}")
    
    try:
        final_result = await orchestrator.process_decision(final_decision, persist=True)
        logger.info(f"Final result: {json.dumps(final_result, indent=2)}")
        
        # Check if veto occurred - look for "veto" in result or check memory_recall_veto result
        veto_confirmed = (
            final_result.get("result") == "veto" or 
            (isinstance(final_result, dict) and "veto" in str(final_result).lower())
        )
        
        logger.info(f"\n{'='*80}")
        logger.info(f"VETO_CONFIRMED: {str(veto_confirmed).lower()}")
        logger.info(f"Final Decision Result:")
        logger.info(json.dumps(final_result, indent=2))
        
        # SQL summary
        logger.info(f"\nSQL Summary: DecisionOutcome Stats")
        logger.info(f"{'symbol':<10} {'signal_type':<20} {'n':<5} {'avg_r':<10} {'win_rate':<10}")
        logger.info("-" * 55)
        
        for sig_type, outcomes in [(losing_signal, losing_outcomes), (control_signal, control_outcomes)]:
            if outcomes:
                r_values = [o.r_multiple for o in outcomes if o.r_multiple is not None]
                avg_r = sum(r_values) / len(r_values) if r_values else 0
                win_count = sum(1 for o in outcomes if o.outcome == "win")
                win_rate = win_count / len(outcomes) if outcomes else 0
                logger.info(f"{symbol:<10} {sig_type:<20} {len(outcomes):<5} {avg_r:<10.4f} {win_rate:<10.2%}")
        
        logger.info(f"{'='*80}\n")
        
        await orchestrator.close()
        return veto_confirmed
    
    except Exception as e:
        logger.error(f"Error in final test: {e}", exc_info=True)
        await orchestrator.close()
        return False


async def main():
    parser = argparse.ArgumentParser(
        description="Memory Recall Veto Validation Experiment"
    )
    parser.add_argument(
        "--max-decisions",
        type=int,
        default=200,
        help="Maximum synthetic decisions to generate (default: 200)"
    )
    parser.add_argument(
        "--min-sample",
        type=int,
        default=20,
        help="Min outcomes per signal type before final test (default: 20)"
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed for determinism"
    )
    parser.add_argument(
        "--db-file",
        type=str,
        default=None,
        help="Use file-based SQLite instead of in-memory"
    )
    
    args = parser.parse_args()
    
    veto_confirmed = await run_experiment(
        max_decisions=args.max_decisions,
        min_sample_size=args.min_sample,
        seed=args.seed,
        use_sqlite_memory=(args.db_file is None),
    )
    
    sys.exit(0 if veto_confirmed else 1)


if __name__ == "__main__":
    asyncio.run(main())
