from typing import Any, Dict

def build_smc_prompt(context: Dict[str, Any]) -> str:
    """
    Build a strict-JSON prompt for the LLM, instructing it to return only valid JSON per schema.
    """
    return (
        "You are an SMC trading signal evaluator. "
        "Given the following context, return STRICT JSON ONLY matching the provided schema. "
        "Do not include markdown, prose, or any text outside the JSON object. "
        "Weigh evidence adaptively: if bias, liquidity, and POI align but LTF is tentative, allow 'strong' tier with rationale. "
        "If uncertain, set action to 'wait'.\n\n"
        "Schema:\n"
        "{\n"
        "  \"metadata\": {\"symbol\": str, \"timeframe_context\": [str], \"timestamp\": str},\n"
        "  \"checklist\": [\n"
        "    {\"key\": str, \"status\": \"met|partial|not_met\", \"rationale\": str}, ...\n"
        "  ],\n"
        "  \"confidence_score\": int (0-100),\n"
        "  \"opportunity_tier\": \"strong|moderate|weak\",\n"
        "  \"action\": \"long|short|wait\",\n"
        "  \"risk\": {\"stop_loss\": float, \"take_profit\": float, \"rr_min\": float, \"risk_per_trade\": float}\n"
        "}\n\n"
        f"Context:\n{context}\n"
        "Return STRICT JSON only."
    )
