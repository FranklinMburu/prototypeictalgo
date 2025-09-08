from typing import Any
from apps.smc.models import SMCDecision
from ict_trading_system.src.utils.logger import setup_logging
import logging

setup_logging()

class SMCNotifier:
    def __init__(self, notifiers: list[Any]):
        self.notifiers = notifiers

    async def notify(self, decision: SMCDecision, context: dict[str, Any]) -> None:
        msg = self.format_message(decision, context)
        for notifier in self.notifiers:
            try:
                await notifier.send(msg)
            except Exception as e:
                logging.error(f"SMCNotifier failed: {notifier.__class__.__name__}: {e}")

    def format_message(self, decision: SMCDecision, context: dict[str, Any]) -> str:
        meta = decision.metadata
        checklist_str = [f"{c.key}={c.status}" for c in decision.checklist]
        return (
            f"[SMC] {meta.symbol} {meta.timeframe_context} @ {meta.timestamp}\n"
            f"Tier: {decision.opportunity_tier} | Action: {decision.action} | Score: {decision.confidence_score}\n"
            f"Checklist: {checklist_str}\n"
            f"Risk: SL={decision.risk.stop_loss} TP={decision.risk.take_profit} RR={decision.risk.rr_min} Risk%={decision.risk.risk_per_trade}"
        )
