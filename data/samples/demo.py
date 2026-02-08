"""CLI demo to build a decision and optionally persist and notify."""

from __future__ import annotations
import argparse
import asyncio
import json
from datetime import datetime, timezone
import os

from reasoner_service.logging_setup import logger
from reasoner_service.alerts import SlackNotifier, DiscordNotifier, TelegramNotifier
import reasoner_service.storage as storage
import config

async def main():
    parser = argparse.ArgumentParser(description="Demo notifier CLI")
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--recommendation", required=True, choices=["enter", "wait_for_breakout", "do_nothing"])
    parser.add_argument("--bias", default="neutral")
    parser.add_argument("--confidence", type=float, default=0.5)
    parser.add_argument("--duration-ms", type=int, default=0)
    parser.add_argument("--repair-used", action="store_true")
    parser.add_argument("--fallback-used", action="store_true")
    parser.add_argument("--summary", default="")
    parser.add_argument("--slack", action="store_true")
    parser.add_argument("--discord", action="store_true")
    parser.add_argument("--telegram", action="store_true")
    parser.add_argument("--persist", action="store_true")
    parser.add_argument("--dsn", default=os.getenv("POSTGRES_URI", ""))
    args = parser.parse_args()

    now_iso = datetime.now(timezone.utc).isoformat()
    decision = {
        "symbol": args.symbol,
        "recommendation": args.recommendation,
        "bias": args.bias,
        "confidence": max(0.0, min(1.0, args.confidence)),
        "duration_ms": int(args.duration_ms),
        "timestamp": now_iso,
        "summary": args.summary,
        "repair_used": bool(args.repair_used),
        "fallback_used": bool(args.fallback_used),
    }

    engine = None
    decision_id = None
    if args.persist:
        if not args.dsn:
            print("POSTGRES DSN required for --persist (use --dsn or POSTGRES_URI env var)")
        else:
            engine = storage.create_engine_from_env_or_dsn(args.dsn)
            await storage.init_models(engine)
            decision_text = json.dumps(decision, ensure_ascii=False)
            decision_id = await storage.insert_decision(
                engine,
                symbol=decision["symbol"],
                decision_text=decision_text,
                raw=decision,
                bias=decision["bias"],
                confidence=decision["confidence"],
                recommendation=decision["recommendation"],
                repair_used=decision["repair_used"],
                fallback_used=decision["fallback_used"],
                duration_ms=decision["duration_ms"],
            )
            print(f"Persisted decision id={decision_id}")

    # determine channels: if no channel flags provided, default to all
    channel_flags = [args.slack, args.discord, args.telegram]
    if not any(channel_flags):
        selected = ["slack", "discord", "telegram"]
    else:
        selected = []
        if args.slack:
            selected.append("slack")
        if args.discord:
            selected.append("discord")
        if args.telegram:
            selected.append("telegram")

    # instantiate notifiers with engine where available
    tasks = []
    for ch in selected:
        if ch == "slack":
            notifier = SlackNotifier(engine=engine)
            tasks.append(notifier.notify(decision, decision_id=decision_id))
        if ch == "discord":
            notifier = DiscordNotifier(engine=engine)
            tasks.append(notifier.notify(decision, decision_id=decision_id))
        if ch == "telegram":
            notifier = TelegramNotifier(engine=engine)
            tasks.append(notifier.notify(decision, decision_id=decision_id))
    if tasks:
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for ch, res in zip(selected, results):
            print(f"{ch}: {res}")
    else:
        print("No channels selected; nothing to send")

if __name__ == "__main__":
    asyncio.run(main())
