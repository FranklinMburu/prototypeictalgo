from typing import Any, Dict, Optional
from apps.smc.models import SMCDecision
from apps.smc.prompt import build_smc_prompt
from apps.smc.llm_client import LLMProvider, FakeLLM

import json
from ict_trading_system.src.utils.logger import setup_logging
import logging
from prometheus_client import Counter, Histogram

smc_evaluations_total = Counter('smc_evaluations_total', 'Total SMC evaluations')
smc_fallback_invoked = Counter('smc_fallback_invoked', 'SMC fallback invoked')
smc_tier_distribution = Counter('smc_tier_distribution', 'SMC decision tier', ['tier'])
smc_eval_latency_seconds = Histogram('smc_eval_latency_seconds', 'SMC evaluation latency (seconds)')

setup_logging()

class SMCDecisionEngine:
    def __init__(self, llm: Optional[LLMProvider] = None):
        self.llm = llm or FakeLLM()

    async def evaluate(self, context: Dict[str, Any]) -> SMCDecision:
        import time
        smc_evaluations_total.inc()
        start = time.perf_counter()
        prompt = build_smc_prompt(context)
        # 1st attempt: LLM
        output = await self.llm.complete(prompt)
        try:
            decision = SMCDecision.model_validate_json(output)
            smc_tier_distribution.labels(tier=decision.opportunity_tier).inc()
            smc_eval_latency_seconds.observe(time.perf_counter() - start)
            return decision
        except Exception as e:
            logging.warning(f"SMC LLM output invalid, attempting repair: {e}")
            # 2nd attempt: repair
            repair_prompt = (
                prompt +
                "\n\nYour previous output was invalid. Return STRICT JSON only, matching the schema exactly."
            )
            repaired = await self.llm.complete(repair_prompt)
            try:
                decision = SMCDecision.model_validate_json(repaired)
                smc_tier_distribution.labels(tier=decision.opportunity_tier).inc()
                smc_eval_latency_seconds.observe(time.perf_counter() - start)
                return decision
            except Exception as e2:
                logging.error(f"SMC LLM repair failed, using fallback: {e2}")
                smc_fallback_invoked.inc()
                # Fallback: minimal compliant decision
                decision = self.fallback_decision(context)
                smc_tier_distribution.labels(tier=decision.opportunity_tier).inc()
                smc_eval_latency_seconds.observe(time.perf_counter() - start)
                return decision

    def fallback_decision(self, context: Dict[str, Any]) -> SMCDecision:
        symbol = context.get("symbol", "XAUUSD")
        now = context.get("timestamp", "2025-08-11T12:00:00Z")
        tf = context.get("timeframe_context", ["4H","1H","5M"])
        keys = ["htf_bias","liquidity_context","poi","ltf_confirmation","risk_execution","discipline","session_killzone"]
        met = {k: context.get(k, True) for k in keys}
        checklist = [
            {"key":k, "status":"met" if met[k] else "not_met", "rationale":"fallback"} for k in keys
        ]
        # Checklist scoring
        met_count = sum(1 for k in keys if met[k])
        checklist_score = met_count / len(keys)
        # Weight liquidity_context and poi
        liquidity_weight = 0.15 if met["liquidity_context"] else 0.0
        poi_weight = 0.15 if met["poi"] else 0.0
        combined_score = min(checklist_score + liquidity_weight + poi_weight, 1.0)
        # Tier thresholds
        if combined_score >= 0.8:
            tier = "strong"
        elif combined_score >= 0.6:
            tier = "moderate"
        else:
            tier = "weak"
        # Action logic
        action = "long" if met["htf_bias"] else "wait"
        # Confidence score
        conf = int(90 * combined_score) if tier == "strong" else (int(70 * combined_score) if tier == "moderate" else int(40 * combined_score))
        # Rationale
        rationale = (
            f"Checklist score: {checklist_score:.2f}, liquidity_weight: {liquidity_weight}, poi_weight: {poi_weight}, "
            f"combined: {combined_score:.2f} → tier: {tier}"
        )
        logging.info(f"[SMC Fallback] {symbol} rationale: {rationale}")
        risk = {"stop_loss":0.2, "take_profit":0.6, "rr_min":3.0, "risk_per_trade":1.0}
        return SMCDecision.model_validate({
            "metadata": {"symbol":symbol, "timeframe_context":tf, "timestamp":now},
            "checklist": checklist,
            "confidence_score": conf,
            "opportunity_tier": tier,
            "action": action,
            "risk": risk,
            "tier_rationale": rationale,
            "checklist_score": round(checklist_score, 2)
        })
