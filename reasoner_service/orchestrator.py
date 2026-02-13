from __future__ import annotations

import asyncio
import json
import os
import time
from typing import Optional, Dict, Any, List, Tuple, Union
from types import SimpleNamespace
from datetime import datetime, time as dt_time, timezone

from .config import get_settings
from .plan_execution_schemas import Plan, ExecutionContext, PlanResult, PlanExecutor
from .orchestrator_events import Event, EventResult
from .reasoning_manager import ReasoningManager, AdvisorySignal
from .reasoning_mode_selector import (
    ReasoningModeSelector, HTFBiasState, ReasoningMode, ModeSelectionError
)
from .orchestration_advanced import (
    OrchestrationStateManager, CooldownConfig, SessionWindow,
    SignalFilter, EventState
)
try:
    import redis.asyncio as aioredis
except Exception:
    aioredis = None
from .storage import (
    create_engine_from_env_or_dsn, create_engine_and_sessionmaker, init_models, insert_decision, compute_decision_hash,
    get_outcomes_by_signal_type
)
from .alerts import SlackNotifier, DiscordNotifier, TelegramNotifier
from .metrics import start_metrics_server_if_enabled, decisions_processed_total, deduplicated_decisions_total, dlq_retries_total, dlq_size, redis_reconnect_attempts
from .logging_setup import logger
from .metrics_snapshot import load_metrics_snapshot
from .policy import outcome_policy, memory_policy
from .allowlist_loader import AllowlistLoader
from utils.redis_wrapper import redis_op

_cfg = get_settings()


class PolicyStore:
    """Facade for pluggable policy backends with chained fallback.

    PolicyStore coordinates multiple backends (config, HTTP, Redis, markers)
    and falls back through them in order until a policy is found. This enables
    authoritative policy services while maintaining backward-compatibility.
    """
    def __init__(self, orch: "DecisionOrchestrator", backends=None):
        """Initialize PolicyStore with optional custom backends.

        Args:
            orch: Reference to DecisionOrchestrator
            backends: Optional list of PolicyBackend instances; if None, uses defaults
        """
        self.orch = orch
        if backends is None:
            # Default backend chain: orchestrator config -> marker fallback
            from .policy_backends import OrchestratorConfigBackend, DefaultPolicyBackend
            backends = [
                OrchestratorConfigBackend(orch),
                DefaultPolicyBackend(),
            ]
        self.backends = backends

    async def get_policy(self, policy_name: str, context: dict) -> dict:
        """Get policy from backends in priority order.

        Tries each backend until one returns a non-empty result. This allows
        orchestrator config to override markers, HTTP services to override local
        config, and so on.
        """
        for backend in self.backends:
            try:
                result = await backend.get_policy(policy_name, context)
                if result:  # Non-empty dict means policy found
                    return result
            except Exception:
                continue
        # Fallback: empty dict (policy not configured)
        return {}


class DecisionOrchestrator:
    def __init__(self, dsn: Optional[str] = None):
        self.dsn = dsn
        self.engine = None
        self._sessionmaker = None
        self.notifiers = {}
        self._dedup = {}  # hash -> ts
        self._lock = asyncio.Lock()
        # lock protecting the in-memory DLQ
        self._dlq_lock = asyncio.Lock()
        # in-memory DLQ for failed persistence attempts (non-blocking fallback)
        # each entry: {decision, error, ts, attempts:int, next_attempt_ts:float}
        self._persist_dlq = []
        # redis client will be set in setup() if enabled
        self._redis = None
        # background task for retrying DLQ entries
        self._dlq_task = None
        # simple circuit-breaker state for redis reconnects
        self._redis_failure_count = 0
        self._redis_circuit_open_until = 0.0
        # routing caches (safe defaults if not provided via config helpers)
        try:
            # some repos provide helper loaders; try importing dynamically
            from .config import load_routing_rules as _lr, load_routing_overrides as _lo
            self._routing_rules = _lr()
            self._routing_overrides = _lo()
        except Exception:
            self._routing_rules = {}
            self._routing_overrides = []
        # Lightweight reasoner adapter exposing a coroutine `call(prompt, signal, decision)`.
        # This delegates to the repository's existing reasoning path and does not bypass
        # orchestration policy or enforcement.
        async def _reasoner_call(prompt, signal=None, decision=None):
            snap: Dict[str, Any] = {}
            try:
                if isinstance(signal, dict):
                    snap.update(signal)
                if isinstance(decision, dict):
                    snap.update(decision)
                if prompt is not None:
                    # preserve prompt for downstream reasoner implementations
                    snap.setdefault("prompt", prompt)
                    snap.setdefault("summary", str(prompt))
                # delegate to existing reasoning implementation
                from .reasoner import reason_from_snapshot

                return await reason_from_snapshot(snap)
            except Exception as e:
                logger.exception("reasoner adapter call failed: %s", e)
                return {"error": str(e)}

        self.reasoner = SimpleNamespace(call=_reasoner_call)
        # attach default policy store (can be overridden in tests)
        self.policy_store = PolicyStore(self)
        # policy counters and audit (permissive by default; enabled for Level-2 enforcement)
        self._policy_counters = {"pass": 0, "veto": 0, "defer": 0}
        self._policy_audit = []
        # outcome metrics snapshot (optional)
        self._metrics_snapshot = {}
        # optional constraints loaded by callers/tests (default empty)
        self._constraints = {}
        # reasoning manager for bounded advisory signal generation
        self.reasoning_manager: Optional[ReasoningManager] = None
        # Stage 4: Reasoning Mode Selector (deterministic mode selection)
        self.reasoning_mode_selector = ReasoningModeSelector()
        # advanced event-driven orchestration
        self.orchestration_state = OrchestrationStateManager()
        self.signal_filter = SignalFilter(policy_store=self.policy_store)
        # allowlist gate: load deterministic group key allowlist (fail-open)
        self.allowlist_loader = AllowlistLoader()
        # policy shadow mode for observational evaluation
        from .policy_shadow_mode import get_shadow_mode_manager
        self.shadow_mode_manager = get_shadow_mode_manager()

    # --- Safety helper: normalized dedup key ---
    def _compute_dedup_key(self, decision: Dict[str, Any]) -> str:
        """
        Compute a stable deduplication key that is resilient to small timestamp or floating
        point differences. Rules (in order):
        1. If `idempotency_key` present, use it directly.
        2. If `signal_id` present, use it directly.
        3. Otherwise, normalize by symbol, recommendation, rounded confidence, and
           a timestamp bucket derived from DEDUP_WINDOW_SECONDS.

        Safety: this intentionally avoids including raw `timestamp_ms` or raw floats
        so that near-duplicate signals within the dedup window produce the same key.
        """
        # 1) idempotency
        idem = decision.get("idempotency_key") or decision.get("idempotency") or decision.get("idempotencyKey")
        if idem:
            return f"idem:{str(idem)}"
        # 2) signal id
        sig = decision.get("signal_id") or decision.get("signalId")
        if sig:
            return f"sig:{str(sig)}"
        # 3) normalized bucket
        symbol = str(decision.get("symbol", "UNKNOWN")).upper()
        rec = str(decision.get("recommendation", "")).lower()
        try:
            conf = int(round(float(decision.get("confidence", 0.0)) * 100))
        except Exception:
            conf = 0
        ts_ms = int(decision.get("timestamp_ms", int(time.time() * 1000)))
        bucket_s = max(1, int(get_settings().DEDUP_WINDOW_SECONDS))
        ts_bucket = int((ts_ms // 1000) // bucket_s)
        return f"norm:{symbol}:{rec}:{conf}:{ts_bucket}"

    # --- Policy gate: pre-reasoning hook ---
    async def pre_reasoning_policy_check(self, snapshot: Dict[str, Any], state: Optional[Dict[str, Any]] = None, ctx: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Pre-reasoning policy gate: checks markers for veto/defer.

        This hook consults the PolicyStore for authoritative policy values; falls back
        to context markers when PolicyStore unavailable. Respects ENABLE_PERMISSIVE_POLICY.
        """
        # Respect permissive mode via feature flag: when enabled, policy checks are no-op
        try:
            cfg = get_settings()
            if getattr(cfg, "ENABLE_PERMISSIVE_POLICY", True):
                return {"result": "pass"}
        except Exception:
            return {"result": "pass"}

        if not isinstance(snapshot, dict):
            return {"result": "pass"}

        # Check allowlist gate: deterministic group key filtering
        try:
            allowlist_cfg = self._load_allowlist_config()
            if allowlist_cfg.get("enabled", False):
                # Load allowlist file if not already loaded
                allowlist_path = allowlist_cfg.get("path")
                if allowlist_path and not self.allowlist_loader.is_enabled():
                    self.allowlist_loader.load(allowlist_path)

                # If allowlist loaded, check if group key is allowed
                if self.allowlist_loader.is_enabled():
                    group_key = AllowlistLoader.make_key_from_snapshot(snapshot)
                    if group_key and not self.allowlist_loader.is_allowed(group_key):
                        self._policy_counters["veto"] += 1
                        entry = {
                            "ts": int(time.time() * 1000),
                            "action": "veto",
                            "reason": "not_in_allowlist",
                            "group_key": group_key,
                            "id": snapshot.get("id"),
                        }
                        try:
                            self._policy_audit.append(entry)
                        except Exception:
                            pass
                        logger.warning("Policy veto applied (allowlist): %s", entry)
                        return {"result": "veto", "reason": "not_in_allowlist", "group_key": group_key}
        except Exception as e:
            logger.exception("Allowlist gate check failed (fail-open): %s", e)

        # Check killzone via PolicyStore (with marker fallback)
        try:
            killzone_policy = await self.policy_store.get_policy("killzone", snapshot or {})
            if killzone_policy.get("active"):
                self._policy_counters["veto"] += 1
                entry = {"ts": int(time.time() * 1000), "action": "veto", "reason": "killzone", "id": snapshot.get("id")}
                try:
                    self._policy_audit.append(entry)
                except Exception:
                    pass
                logger.warning("Policy veto applied (killzone): %s", entry)
                return {"result": "veto", "reason": "killzone"}
        except Exception:
            # fallback to marker behavior
            if snapshot.get("killzone"):
                self._policy_counters["veto"] += 1
                entry = {"ts": int(time.time() * 1000), "action": "veto", "reason": "killzone", "id": snapshot.get("id")}
                try:
                    self._policy_audit.append(entry)
                except Exception:
                    pass
                logger.warning("Policy veto applied (killzone marker): %s", entry)
                return {"result": "veto", "reason": "killzone"}

        # Check regime via PolicyStore
        try:
            regime_policy = await self.policy_store.get_policy("regime", snapshot or {})
            if regime_policy.get("regime") == "restricted":
                self._policy_counters["veto"] += 1
                entry = {"ts": int(time.time() * 1000), "action": "veto", "reason": "regime_restricted", "id": snapshot.get("id")}
                try:
                    self._policy_audit.append(entry)
                except Exception:
                    pass
                logger.warning("Policy veto applied (regime): %s", entry)
                return {"result": "veto", "reason": "regime_restricted"}
        except Exception:
            if snapshot.get("regime") == "restricted":
                self._policy_counters["veto"] += 1
                entry = {"ts": int(time.time() * 1000), "action": "veto", "reason": "regime_restricted", "id": snapshot.get("id")}
                try:
                    self._policy_audit.append(entry)
                except Exception:
                    pass
                logger.warning("Policy veto applied (regime marker): %s", entry)
                return {"result": "veto", "reason": "regime_restricted"}

        # Check cooldown via PolicyStore
        try:
            cooldown_policy = await self.policy_store.get_policy("cooldown", snapshot or {})
            cooldown = int(cooldown_policy.get("cooldown_until", 0) or 0)
            now_ms = int(time.time() * 1000)
            if cooldown and cooldown > now_ms:
                # record defer and enqueue to in-memory DLQ for retry
                self._policy_counters["defer"] += 1
                entry = {"ts": int(time.time() * 1000), "action": "defer", "reason": "cooldown", "next_attempt_ts": cooldown, "id": snapshot.get("id")}
                try:
                    self._policy_audit.append(entry)
                except Exception:
                    pass
                logger.info("Policy defer scheduled (cooldown): %s", entry)
                # append DLQ entry for retry (best-effort, non-blocking)
                try:
                    dlq_entry = {"decision": snapshot, "error": "policy_defer", "ts": int(time.time() * 1000), "attempts": 0, "next_attempt_ts": cooldown}
                    try:
                        self._persist_dlq.append(dlq_entry)
                        try:
                            dlq_size.set(len(self._persist_dlq))
                        except Exception:
                            pass
                    except Exception:
                        self._persist_dlq.append(dlq_entry)
                except Exception:
                    logger.exception("failed to append policy-defer to in-memory DLQ")
                return {"result": "defer", "reason": "cooldown", "next_attempt_ts": cooldown}
        except Exception:
            # fallback to marker behavior
            try:
                now_ms = int(time.time() * 1000)
                cooldown = int(snapshot.get("cooldown_until", 0) or 0)
                if cooldown and cooldown > now_ms:
                    self._policy_counters["defer"] += 1
                    entry = {"ts": int(time.time() * 1000), "action": "defer", "reason": "cooldown", "next_attempt_ts": cooldown, "id": snapshot.get("id")}
                    try:
                        self._policy_audit.append(entry)
                    except Exception:
                        pass
                    logger.info("Policy defer scheduled (cooldown marker): %s", entry)
                    try:
                        dlq_entry = {"decision": snapshot, "error": "policy_defer", "ts": int(time.time() * 1000), "attempts": 0, "next_attempt_ts": cooldown}
                        try:
                            self._persist_dlq.append(dlq_entry)
                            try:
                                dlq_size.set(len(self._persist_dlq))
                            except Exception:
                                pass
                        except Exception:
                            self._persist_dlq.append(dlq_entry)
                    except Exception:
                        logger.exception("failed to append policy-defer to in-memory DLQ (marker fallback)")
                    return {"result": "defer", "reason": "cooldown", "next_attempt_ts": cooldown}
            except Exception:
                pass

        # Check exposure via PolicyStore
        try:
            exp_policy = await self.policy_store.get_policy("exposure", snapshot or {})
            exposure = float(exp_policy.get("exposure", 0) or 0)
            max_exposure = float(exp_policy.get("max_exposure", 0) or 0)
            if max_exposure and exposure > max_exposure:
                self._policy_counters["veto"] += 1
                entry = {"ts": int(time.time() * 1000), "action": "veto", "reason": "risk_limit_exceeded", "exposure": exposure, "max_exposure": max_exposure, "id": snapshot.get("id")}
                try:
                    self._policy_audit.append(entry)
                except Exception:
                    pass
                logger.warning("Policy veto applied (exposure): %s", entry)
                return {"result": "veto", "reason": "risk_limit_exceeded", "exposure": exposure, "max_exposure": max_exposure}
        except Exception:
            try:
                exposure = float(snapshot.get("exposure", 0) or 0)
                max_exposure = float(snapshot.get("max_exposure", 0) or 0)
                if max_exposure and exposure > max_exposure:
                    self._policy_counters["veto"] += 1
                    entry = {"ts": int(time.time() * 1000), "action": "veto", "reason": "risk_limit_exceeded", "exposure": exposure, "max_exposure": max_exposure, "id": snapshot.get("id")}
                    try:
                        self._policy_audit.append(entry)
                    except Exception:
                        pass
                    logger.warning("Policy veto applied (exposure marker): %s", entry)
                    return {"result": "veto", "reason": "risk_limit_exceeded", "exposure": exposure, "max_exposure": max_exposure}
            except Exception:
                pass

        # Outcome-aware veto (additive)
        try:
            key = (snapshot.get("symbol"), snapshot.get("model"), snapshot.get("session"))
            outcome_cfg = self._load_outcome_config()
            result = outcome_policy.check_performance(
                key,
                self._metrics_snapshot,
                min_sample_size=int(outcome_cfg.get("min_sample_size", 20)),
                expectancy_threshold=float(outcome_cfg.get("expectancy_threshold", -0.05)),
                win_rate_threshold=float(outcome_cfg.get("win_rate_threshold", 0.45)),
            )
            if result.get("result") == "veto":
                self._policy_counters["veto"] += 1
                self._policy_audit.append({"type": "outcome", **result, "decision_id": snapshot.get("id")})
                return {"result": "veto", "reason": result.get("reason", "outcome_underperformance")}
        except Exception:
            pass

        # Memory-based veto/promote (additive)
        try:
            key = (snapshot.get("symbol"), snapshot.get("model"), snapshot.get("session"))
            mem_cfg = self._load_memory_config()
            mem_res = await memory_policy.check_similarity(
                key,
                self._lookup_similar_signals,
                top_n=int(mem_cfg.get("memory_top_n", 10)),
                negative_threshold=float(mem_cfg.get("negative_threshold", -0.05)),
                positive_threshold=float(mem_cfg.get("positive_threshold", 0.10)),
            )
            if mem_res.get("result") == "veto":
                self._policy_counters["veto"] += 1
                self._policy_audit.append({"type": "memory", **mem_res, "decision_id": snapshot.get("id")})
                return {"result": "veto", "reason": mem_res.get("reason", "memory_underperformance")}
            if mem_res.get("result") == "promote":
                try:
                    ctx = snapshot.setdefault("context", {})
                    ctx["memory_promoted"] = True
                except Exception:
                    pass
        except Exception:
            pass

        # Memory Recall Veto: DB-backed deterministic veto on poor recent performance
        try:
            outcome_adapt_cfg = self._load_outcome_adaptation_config()
            if outcome_adapt_cfg.get("enabled", False):
                symbol = snapshot.get("symbol")
                signal_type = snapshot.get("signal_type")
                model = snapshot.get("model")
                session = snapshot.get("session")
                direction = snapshot.get("direction")
                
                if symbol and signal_type and self._sessionmaker:
                    window_n = int(outcome_adapt_cfg.get("window_last_n_trades", 50))
                    min_sample = int(outcome_adapt_cfg.get("min_sample_size", 20))
                    suppress_expectancy = float(outcome_adapt_cfg.get("suppress_if", {}).get("expectancy_r", -0.05))
                    suppress_win_rate = float(outcome_adapt_cfg.get("suppress_if", {}).get("win_rate", 0.45))
                    
                    # Query recent outcomes for this symbol + signal_type (+ optional model/session/direction)
                    outcomes = await get_outcomes_by_signal_type(
                        self._sessionmaker,
                        symbol=symbol,
                        signal_type=signal_type,
                        limit=window_n,
                        model=model,
                        session_id=session,
                        direction=direction,
                    )
                    
                    if outcomes:
                        # Extract only outcomes with valid r_multiple (ignore missing/invalid)
                        outcome_list = []
                        for o in outcomes:
                            r_mult = o.get("r_multiple")
                            outcome_type = o.get("outcome", "").lower()
                            # Only include if r_multiple is present and numeric
                            if r_mult is not None and isinstance(r_mult, (int, float)):
                                outcome_list.append({"r_multiple": float(r_mult), "outcome": outcome_type})
                        
                        # Compute metrics for all outcomes with valid r_multiple
                        expectancy, win_rate, sample_size = self._compute_expectancy_and_win_rate(outcome_list)
                        details = {
                            "expectancy": expectancy,
                            "win_rate": win_rate,
                            "sample_size": sample_size,
                            "thresholds": {
                                "expectancy_threshold": suppress_expectancy,
                                "win_rate_threshold": suppress_win_rate,
                            }
                        }
                        
                        # Veto only if we have sufficient sample size of valid outcomes AND poor performance
                        if sample_size >= min_sample:
                            if expectancy < suppress_expectancy or win_rate < suppress_win_rate:
                                self._policy_counters["veto"] += 1
                                self._policy_audit.append({
                                    "type": "memory_recall",
                                    "reason": "memory_underperformance",
                                    "decision_id": snapshot.get("id"),
                                    **details
                                })
                                logger.warning(f"Memory recall veto: {symbol}/{signal_type} model={model} session={session} direction={direction} expectancy={expectancy:.2f}, wr={win_rate:.2f}")
                                return {
                                    "result": "veto",
                                    "reason": "memory_underperformance",
                                    "details": details
                                }
                            else:
                                # Good performance, pass
                                return {
                                    "result": "pass",
                                    "details": details
                                }
                        else:
                            # Insufficient sample size, pass
                            return {
                                "result": "pass",
                                "details": details
                            }
        except Exception as e:
            logger.warning(f"Memory recall veto check failed: {e}", exc_info=True)
            # Fail open: log warning but continue

        self._policy_counters["pass"] += 1
        # Return pass with empty details if no memory adaptation occurred
        return {"result": "pass", "details": {"sample_size": 0, "expectancy": 0.0, "win_rate": 0.0}}

    def _load_outcome_config(self) -> Dict[str, Any]:
        return getattr(self, "_constraints", {}).get("outcome_veto", {})

    def _load_memory_config(self) -> Dict[str, Any]:
        return getattr(self, "_constraints", {}).get("memory_veto", {})

    def _load_outcome_adaptation_config(self) -> Dict[str, Any]:
        """Load outcome_adaptation config for memory recall veto."""
        return getattr(self, "_constraints", {}).get("outcome_adaptation", {})

    def _load_allowlist_config(self) -> Dict[str, Any]:
        """Load allowlist gate config."""
        return getattr(self, "_constraints", {}).get("allowlist", {})

    def _compute_expectancy_and_win_rate(self, outcomes: List[Dict[str, Any]]) -> Tuple[float, float, int]:
        """
        Compute expectancy (mean r_multiple) and win rate from outcomes.
        
        Returns:
            (expectancy, win_rate, sample_size)
        """
        if not outcomes:
            return 0.0, 0.0, 0
        
        valid_outcomes = [o for o in outcomes if isinstance(o.get("r_multiple"), (int, float))]
        if not valid_outcomes:
            return 0.0, 0.0, 0
        
        expectancy = sum(o["r_multiple"] for o in valid_outcomes) / len(valid_outcomes)
        win_count = sum(1 for o in valid_outcomes if o.get("outcome", "").lower() == "win")
        win_rate = win_count / len(valid_outcomes) if valid_outcomes else 0.0
        
        return expectancy, win_rate, len(valid_outcomes)

    async def _lookup_similar_signals(
        self, key: Tuple[str, str, str], top_n: int
    ) -> List[Dict[str, Any]]:
        """
        Query DecisionOutcome table for recent similar trades.
        
        Similarity key: (symbol, signal_type) - deterministic DB lookup.
        Returns outcomes ordered by timestamp DESC.
        
        Args:
            key: Tuple of (symbol, signal_type, session) - uses symbol + signal_type
            top_n: Max outcomes to return
        
        Returns:
            List of outcome dicts with: pnl, outcome (win/loss/breakeven), closed_at, etc.
            Returns empty list if sessionmaker unavailable or DB query fails.
        """
        try:
            if not self._sessionmaker:
                logger.warning("Memory recall: sessionmaker not available, returning empty")
                return []
            
            symbol, signal_type, session = key
            outcomes = await get_outcomes_by_signal_type(
                self._sessionmaker,
                symbol=symbol,
                signal_type=signal_type,
                limit=top_n,
            )
            # Convert outcome field to r_multiple-like metric: 1.0 for win, -1.0 for loss, 0.0 for breakeven
            results = []
            for outcome in outcomes:
                outcome_type = outcome.get("outcome", "").lower()
                if outcome_type == "win":
                    r_multiple = max(1.0, float(outcome.get("pnl", 0.0)) / 10.0)  # Normalize PnL to r_multiple
                elif outcome_type == "loss":
                    r_multiple = min(-1.0, float(outcome.get("pnl", 0.0)) / 10.0)
                else:
                    r_multiple = 0.0
                
                results.append({
                    "r_multiple": r_multiple,
                    "outcome": outcome_type,
                    "pnl": outcome.get("pnl", 0.0),
                    "timestamp": outcome.get("closed_at"),
                    "signal_type": outcome.get("signal_type"),
                    "symbol": outcome.get("symbol"),
                })
            return results
        except Exception as e:
            logger.warning(f"Memory recall DB query failed: {e}", exc_info=True)
            return []

    # --- Policy gate: post-reasoning hook ---
    async def post_reasoning_policy_check(self, reasoning_output: Dict[str, Any], state: Optional[Dict[str, Any]] = None, ctx: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Post-reasoning policy gate: checks confidence and other advisory outputs.

        This hook consults PolicyStore for confidence thresholds and can veto low-confidence
        enter decisions. Respects ENABLE_PERMISSIVE_POLICY.
        """
        # Respect permissive mode via feature flag
        try:
            cfg = get_settings()
            if getattr(cfg, "ENABLE_PERMISSIVE_POLICY", True):
                return {"result": "pass"}
        except Exception:
            return {"result": "pass"}

        if not isinstance(reasoning_output, dict):
            return {"result": "pass"}

        # Example veto paths based on recommendation or confidence; consult PolicyStore
        rec = str(reasoning_output.get("recommendation", "")).lower()
        try:
            confidence = float(reasoning_output.get("confidence", 0) or 0)
        except Exception:
            confidence = 0

        try:
            conf_policy = await self.policy_store.get_policy("confidence_threshold", reasoning_output or {})
            min_conf = float(conf_policy.get("min_confidence", 0.5) or 0.5)
            if rec == "enter" and confidence < min_conf:
                self._policy_counters["veto"] += 1
                entry = {"ts": int(time.time() * 1000), "action": "veto", "reason": "low_confidence", "confidence": confidence, "id": reasoning_output.get("id")}
                try:
                    self._policy_audit.append(entry)
                except Exception:
                    pass
                logger.warning("Policy veto applied (confidence): %s", entry)
                return {"result": "veto", "reason": "low_confidence"}
        except Exception:
            if rec == "enter" and confidence < 0.5:
                self._policy_counters["veto"] += 1
                entry = {"ts": int(time.time() * 1000), "action": "veto", "reason": "low_confidence", "confidence": confidence, "id": reasoning_output.get("id")}
                try:
                    self._policy_audit.append(entry)
                except Exception:
                    pass
                logger.warning("Policy veto applied (confidence marker): %s", entry)
                return {"result": "veto", "reason": "low_confidence"}

        # Allow other advisory outputs
        self._policy_counters["pass"] += 1
        return {"result": "pass"}

    async def _execute_paper_trade_if_enabled(self, decision: Dict[str, Any]) -> Optional[str]:
        """
        Execute a simulated paper trade when enabled (feature-flagged).
        
        Called after a PASS decision to:
        1. Simulate order entry with slippage
        2. Simulate TP/SL hit
        3. Record outcome via outcome_recorder
        
        Returns:
            outcome_id if trade was recorded, None if disabled or error
        
        Non-blocking: Errors logged but don't interrupt orchestration
        """
        try:
            # Load paper adapter config
            paper_cfg = self._load_paper_adapter_config()
            if not paper_cfg.get("enabled", False):
                return None
            
            # Check required fields for paper trading
            symbol = decision.get("symbol")
            signal_type = decision.get("signal_type")
            timeframe = decision.get("timeframe")
            direction = decision.get("direction", "long")
            entry_price = decision.get("entry_price")
            sl_price = decision.get("stop_loss_price") or decision.get("sl_price")
            tp_price = decision.get("take_profit_price") or decision.get("tp_price")
            decision_id = decision.get("id")
            
            if not all([symbol, signal_type, timeframe, entry_price, sl_price, tp_price, decision_id]):
                logger.debug("Paper adapter: Missing required fields, skipping execution")
                return None
            
            # Initialize adapter and execute
            from .paper_execution_adapter import BrokerSimulatorAdapter, PaperExecutionConfig
            
            # Build adapter config from constraints
            adapter_config = PaperExecutionConfig(
                slippage_model=paper_cfg.get("slippage_model", "fixed_percent"),
                slippage_fixed_pct=float(paper_cfg.get("slippage_fixed_pct", 0.05)),
                slippage_random_min_pct=float(paper_cfg.get("slippage_random_min_pct", 0.0)),
                slippage_random_max_pct=float(paper_cfg.get("slippage_random_max_pct", 0.1)),
                tpsl_model=paper_cfg.get("tpsl_model", "random_bars"),
                tpsl_random_bars_min=int(paper_cfg.get("tpsl_random_bars_min", 5)),
                tpsl_random_bars_max=int(paper_cfg.get("tpsl_random_bars_max", 100)),
                tpsl_random_hours_min=int(paper_cfg.get("tpsl_random_hours_min", 1)),
                tpsl_random_hours_max=int(paper_cfg.get("tpsl_random_hours_max", 24)),
                assume_fill_on_signal=bool(paper_cfg.get("assume_fill_on_signal", True)),
                fill_delay_seconds=int(paper_cfg.get("fill_delay_seconds", 2)),
                seed=paper_cfg.get("seed"),
            )
            
            adapter = BrokerSimulatorAdapter(adapter_config)
            
            # Execute paper trade
            result = await adapter.execute_entry(
                decision_id=decision_id,
                symbol=symbol,
                signal_type=signal_type,
                timeframe=timeframe,
                entry_price=entry_price,
                sl_price=sl_price,
                tp_price=tp_price,
                direction=direction,
                model=decision.get("model"),
                session=decision.get("session"),
            )
            
            # Record outcome via outcome_recorder
            if not self._sessionmaker:
                logger.warning("Paper adapter: sessionmaker not available, outcome not recorded")
                return None
            
            from .outcome_recorder import create_outcome_recorder
            recorder = await create_outcome_recorder(self._sessionmaker)
            
            outcome_args = result.to_outcome_recorder_args()
            outcome_id = await recorder.record_trade_outcome(**outcome_args)
            
            logger.info(f"Paper trade recorded: outcome_id={outcome_id}")
            return outcome_id
        
        except Exception as e:
            logger.exception(f"Paper trade execution error (non-blocking): {e}")
            return None

    def _load_paper_adapter_config(self) -> Dict[str, Any]:
        """Load paper_execution_adapter config from constraints."""
        return getattr(self, "_constraints", {}).get("paper_execution_adapter", {})

    def _select_reasoning_mode(
        self,
        decision: Dict[str, Any],
        event: Event
    ) -> Union[ReasoningMode, EventResult]:
        """Stage 4: Select reasoning mode based on HTF bias and position state.
        
        Returns:
            Selected mode string if successful
            EventResult(status='rejected') if mode selection fails
        """
        # Extract state
        htf_bias_state_str = decision.get("htf_bias_state")
        position_open = decision.get("position_open", False)
        decision_id = decision.get("id", event.correlation_id)
        
        # Validate inputs
        if htf_bias_state_str is None:
            logger.error(
                "Stage 4: htf_bias_state missing (decision: %s)",
                decision_id
            )
            return EventResult(
                status="rejected",
                reason="mode_selection_failed",
                metadata={"error": "htf_bias_state_missing"}
            )
        
        try:
            htf_bias_state = HTFBiasState(htf_bias_state_str)
        except ValueError:
            logger.error(
                "Stage 4: invalid htf_bias_state='%s' (decision: %s)",
                htf_bias_state_str,
                decision_id
            )
            return EventResult(
                status="rejected",
                reason="mode_selection_failed",
                metadata={"error": f"invalid_htf_bias_state:{htf_bias_state_str}"}
            )
        
        # Select mode
        try:
            result = self.reasoning_mode_selector.select_mode(
                htf_bias_state=htf_bias_state,
                position_open=position_open
            )
            if result.error:
                logger.error(
                    "Stage 4: mode selection error: %s (decision: %s)",
                    result.error,
                    decision_id
                )
                return EventResult(
                    status="rejected",
                    reason="mode_selection_failed",
                    metadata={"error": result.error}
                )
            return result.mode
        except ModeSelectionError as e:
            logger.error(
                "Stage 4: %s (decision: %s)",
                e.message,
                decision_id
            )
            return EventResult(
                status="rejected",
                reason="mode_selection_failed",
                metadata={"error": e.message}
            )

    async def setup(self):
        # Create async engine and sessionmaker pair. Use sessionmaker for persistence calls.
        try:
            engine, sessionmaker = await create_engine_and_sessionmaker(self.dsn)
            self.engine = engine
            self._sessionmaker = sessionmaker
            await init_models(self.engine)
        except Exception:
            # Fallback to older helper (engine-only). This keeps changes additive and safe.
            self.engine = create_engine_from_env_or_dsn(self.dsn)
            await init_models(self.engine)
        self.notifiers = {
            "slack": SlackNotifier(_cfg.SLACK_WEBHOOK_URL, engine=self.engine),
            "discord": DiscordNotifier(_cfg.DISCORD_WEBHOOK_URL, engine=self.engine),
            "telegram": TelegramNotifier(_cfg.TELEGRAM_TOKEN, _cfg.TELEGRAM_CHAT_ID, engine=self.engine),
        }
        start_metrics_server_if_enabled()
        # load optional metrics snapshot for outcome-aware policy
        try:
            metrics_path = os.getenv("METRICS_SNAPSHOT_PATH", "")
            if metrics_path:
                self._metrics_snapshot = load_metrics_snapshot(metrics_path)
        except Exception:
            pass
        # setup optional Redis DLQ with backoff
        try:
            if _cfg.REDIS_DLQ_ENABLED and aioredis is not None:
                await self._ensure_redis()
        except Exception:
            logger.exception("error while configuring Redis DLQ")

        # Initialize policy shadow mode for observational evaluation
        try:
            from .policy_shadow_mode import initialize_shadow_mode
            from .outcome_stats import create_stats_service
            stats_service = create_stats_service(self._sessionmaker or self.engine)
            success = await initialize_shadow_mode(stats_service)
            if success:
                logger.info("Policy shadow mode initialized successfully")
            else:
                logger.warning("Policy shadow mode initialization failed or skipped")
        except Exception:
            logger.exception("Error initializing policy shadow mode (non-blocking)")

        # start DLQ retry loop if enabled (either redis or in-memory)
        try:
            if _cfg.DLQ_POLL_INTERVAL_SECONDS and (_cfg.REDIS_DLQ_ENABLED and self._redis is not None or _cfg.DLQ_POLL_INTERVAL_SECONDS):
                # run background retry loop
                self._dlq_task = asyncio.create_task(self._dlq_retry_loop())
        except Exception:
            logger.exception("failed to start DLQ retry task")

    def _is_quiet_hours(self, now: Optional[datetime] = None) -> bool:
        q = _cfg.QUIET_HOURS
        if not q:
            return False
        try:
            now = now or datetime.utcnow()
            parts = q.split("-")
            start = parts[0].strip()
            end = parts[1].strip()
            sh, sm = map(int, start.split(":"))
            eh, em = map(int, end.split(":"))
            t = now.time()
            start_t = dt_time(sh, sm)
            end_t = dt_time(eh, em)
            if start_t < end_t:
                return start_t <= t <= end_t
            else:
                return t >= start_t or t <= end_t
        except Exception:
            return False

    def _normalize_decision(self, decision: Dict[str, Any]) -> Dict[str, Any]:
        d = dict(decision)
        if d.get("symbol"):
            d["symbol"] = str(d["symbol"]).upper()
        else:
            d["symbol"] = "UNKNOWN"
        try:
            conf = float(d.get("confidence", 0.0))
        except Exception:
            conf = 0.0
        d["confidence"] = max(0.0, min(1.0, conf))
        ts = d.get("timestamp") or d.get("timestamp_iso")
        if not ts:
            now = datetime.now(timezone.utc)
            d["timestamp"] = now.isoformat()
            d["timestamp_ms"] = int(now.timestamp() * 1000)
        else:
            try:
                parsed = datetime.fromisoformat(ts) if isinstance(ts, str) else None
                if parsed is None:
                    parsed = datetime.now(timezone.utc)
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                d["timestamp"] = parsed.isoformat()
                d["timestamp_ms"] = int(parsed.timestamp() * 1000)
            except Exception:
                now = datetime.now(timezone.utc)
                d["timestamp"] = now.isoformat()
                d["timestamp_ms"] = int(now.timestamp() * 1000)
        d.setdefault("bias", "neutral")
        d.setdefault("recommendation", "do_nothing")
        d.setdefault("duration_ms", int(d.get("duration_ms", 0) or 0))
        d.setdefault("summary", str(d.get("summary", "")))
        d.setdefault("repair_used", bool(d.get("repair_used", False)))
        d.setdefault("fallback_used", bool(d.get("fallback_used", False)))
        # ensure tags list
        tags = d.get("tags") or []
        if isinstance(tags, str):
            # comma separated
            tags = [t.strip() for t in tags.split(",") if t.strip()]
        d["tags"] = list(tags)
        return d

    def _in_override_window(self, override: Dict[str, Any], now_utc: Optional[datetime] = None) -> bool:
        now = now_utc or datetime.utcnow()
        try:
            start = override.get("start")
            end = override.get("end")
            if not start or not end:
                return False
            sh, sm = map(int, start.split(":"))
            eh, em = map(int, end.split(":"))
            start_t = dt_time(sh, sm)
            end_t = dt_time(eh, em)
            t = now.time()
            if start_t < end_t:
                return start_t <= t <= end_t
            else:
                return t >= start_t or t <= end_t
        except Exception:
            return False

    def _get_routing_for_decision(self, decision: Dict[str, Any]) -> List[str]:
        """Resolve routing channels for a decision using:
           1) time-based overrides for the symbol (UTC)
           2) exact symbol routing rules
           3) tag-based routing rules (key format tag1|tag2 matches if all tags present)
           4) wildcard symbol patterns ending with '*'
        """
        symbol = decision.get("symbol", "")
        tags = set(decision.get("tags", []) or [])

        # 1) overrides
        for ov in self._routing_overrides:
            if ov.get("symbol") == symbol:
                if self._in_override_window(ov):
                    chs = ov.get("channels") or []
                    if isinstance(chs, list) and chs:
                        return chs

        # 2) exact symbol
        rules = self._routing_rules or {}
        if symbol in rules:
            return rules[symbol]

        # 3) tag-based
        matched = []
        for key, chs in rules.items():
            if "|" in key:
                required = {p.strip() for p in key.split("|") if p.strip()}
                if required and required.issubset(tags):
                    matched.extend(chs)
        if matched:
            # return unique preserving order
            return list(dict.fromkeys(matched))

        # 4) wildcard symbol patterns
        for key, chs in rules.items():
            if key.endswith("*") and symbol.startswith(key[:-1]):
                return chs

        # default fallback: all channels
        return ["slack", "discord", "telegram"]

    async def execute_plan_if_enabled(self, plan: Dict[str, Any], execution_ctx: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a plan if enabled, returning a PlanResult.
        
        This method acts as the contract boundary between orchestrator and executor.
        It accepts raw plan/context dicts and returns a PlanResult conforming to 
        PLAN_EXECUTION_CONTRACT.md Section 3.
        
        Raises NotImplementedError: Plan execution logic not yet implemented.
        """
        from .config import get_settings as _get_settings
        
        # Feature flag: if disabled, return empty dict for backward compatibility
        if not getattr(_get_settings(), "ENABLE_PLAN_EXECUTOR", False):
            return {}
        
        # This is the contract boundary: attempt to construct contract-aligned structures.
        # If this raises, it indicates the caller is not providing contract-compliant data.
        try:
            # Note: We do NOT validate here. Validation is the executor's responsibility
            # per Contract Section 2 and Appendix. We only construct the data structures.
            # Converting raw dicts to contract types for the executor.
            
            # Convert plan dict to Plan object (stub - no validation)
            plan_obj = Plan(**plan) if isinstance(plan, dict) else plan
            
            # Convert execution context to ExecutionContext object (stub - no validation)  
            if isinstance(execution_ctx, dict):
                exec_ctx_obj = ExecutionContext(**execution_ctx)
            else:
                exec_ctx_obj = execution_ctx
            
            # Instantiate PlanExecutor and delegate
            executor = PlanExecutor(orchestrator=self)
            result: PlanResult = await executor.execute_plan(exec_ctx_obj)
            
            # Convert PlanResult back to dict for backward compatibility
            # (Future: may return PlanResult directly once callers are updated)
            return {
                "plan_id": result.plan_id,
                "execution_id": result.execution_id,
                "status": result.status,
                "completed_at": result.completed_at,
                "duration_ms": result.duration_ms,
                "steps_executed": result.steps_executed,
                "steps_total": result.steps_total,
                "result_payload": result.result_payload,
                "error": {
                    "error_code": result.error.error_code,
                    "message": result.error.message,
                    "step_id": result.error.step_id,
                    "severity": result.error.severity,
                    "recoverable": result.error.recoverable,
                    "cause": result.error.cause,
                    "context": result.error.context,
                } if result.error else None,
            }
        except NotImplementedError:
            # PlanExecutor raises NotImplementedError - propagate as-is
            raise
        except Exception as e:
            logger.exception("execute_plan_if_enabled failed: %s", e)
            # Return empty dict on unexpected errors (backward compatible)
            return {}

    async def process_decision(self, decision: Dict[str, Any], persist: bool = True, channels: Optional[List[str]] = None) -> Dict[str, Any]:
        # Policy gate: pre-reasoning hook (placeholder)
        try:
            # pass the raw incoming snapshot as-is; state/ctx are intentionally empty for now
            _ = await self.pre_reasoning_policy_check(decision, state={}, ctx=None)
        except Exception as e:
            logger.exception("pre_reasoning_policy_check error: %s", e)

        d = self._normalize_decision(decision)
        # Policy gate: post-reasoning hook (placeholder)
        try:
            # pass the normalized decision as the reasoning output
            _ = await self.post_reasoning_policy_check(d, state={}, ctx=None)
        except Exception as e:
            logger.exception("post_reasoning_policy_check error: %s", e)
        
        # Paper Execution: If enabled, simulate trade execution after PASS
        # This is non-blocking and only executes if feature flag enabled
        try:
            await self._execute_paper_trade_if_enabled(d)
        except Exception as e:
            logger.exception("Paper trade execution error (non-blocking): %s", e)
        
        # SHADOW MODE: Evaluate policies in observation-only mode (non-blocking)
        # Captures VETO decisions for audit trail, does NOT block execution
        shadow_result = None
        try:
            from .policy_shadow_mode import evaluate_decision_shadow
            shadow_result = await evaluate_decision_shadow(
                d,
                signal_type=d.get("signal_type"),
                symbol=d.get("symbol"),
                timeframe=d.get("timeframe"),
            )
            # Attach shadow result to decision for downstream logging/analysis
            if shadow_result:
                d["_shadow_policy_result"] = shadow_result
        except Exception as e:
            logger.exception("Shadow mode evaluation error (non-blocking): %s", e)
            # CRITICAL: Never block execution due to shadow mode errors
        
        symbol = d["symbol"]
        rec = d.get("recommendation")
        conf = float(d.get("confidence", 0.0))
        ts_ms = int(d.get("timestamp_ms", int(time.time() * 1000)))
        # Use normalized dedup key which avoids raw timestamp/float sensitivity
        decision_hash = self._compute_dedup_key(d)
        now_ts = time.time()

        # dedup in-memory
        skipped = False
        if _cfg.DEDUP_ENABLED:
            # try optional Redis-based dedup first (SETNX + EXPIRE)
            if _cfg.REDIS_DEDUP_ENABLED and getattr(self, "_redis", None) is not None:
                try:
                    key = f"{_cfg.REDIS_DEDUP_PREFIX}{decision_hash}"
                    # SETNX equivalent: set with nx=True and expire
                    try:
                        from utils.redis_wrapper import RedisUnavailable, RedisOpFailed
                        _rres = await redis_op(self, lambda r, k, v, ex, nx: r.set(k, v, ex=ex, nx=nx), key, "1", ex=int(_cfg.REDIS_DEDUP_TTL_SECONDS), nx=True)
                        # redis_op returns a dict {ok: True, value: <raw>} for success
                        r = _rres.get("value") if isinstance(_rres, dict) else _rres
                        # many redis clients return True/False for set nx; treat falsy as already present
                        if not r:
                            deduplicated_decisions_total.inc()
                            skipped = True
                    except (RedisUnavailable, RedisOpFailed):
                        # fallback to in-memory dedup if redis op fails
                        pass
                    except Exception:
                        # any other redis error -> fallback to in-memory
                        pass
                    else:
                        # marked in redis; continue processing
                        pass
                except Exception:
                    # fallback to in-memory dedup on redis error
                    pass

        # persist
        dec_id = None
        if persist:
            try:
                # Prefer sessionmaker-based persistence (sessionmaker is created in setup)
                session_arg = self._sessionmaker if self._sessionmaker is not None else self.engine
                dec_id = await insert_decision(session_arg, symbol=symbol, decision_text=json.dumps(d), raw=d, bias=d.get("bias","neutral"), confidence=conf, recommendation=rec, repair_used=bool(d.get("repair_used")), fallback_used=bool(d.get("fallback_used")), duration_ms=int(d.get("duration_ms",0)), ts_ms=ts_ms)
                decisions_processed_total.labels(result="persisted").inc()
            except Exception as e:
                decisions_processed_total.labels(result="failed").inc()
                logger.exception("persist failure: %s", e)
                # Non-blocking fallback: enqueue decision to in-memory DLQ for later retry
                try:
                    # annotate DLQ entry with attempts and schedule for immediate retry
                    entry = {"decision": d, "error": str(e), "ts": int(time.time() * 1000), "attempts": 0, "next_attempt_ts": 0.0}
                    if _cfg.REDIS_DLQ_ENABLED and self._redis is not None:
                        # push JSON serialized entry to Redis list (RPUSH)
                        try:
                            from utils.redis_wrapper import RedisUnavailable, RedisOpFailed
                            await redis_op(self, lambda r, key, v: r.rpush(key, v), _cfg.REDIS_DLQ_KEY, json.dumps(entry))
                            # update dlq size metric if available
                            try:
                                llen = await redis_op(self, lambda r, key: r.llen(key), _cfg.REDIS_DLQ_KEY)
                                try:
                                    dlq_size.set(llen)
                                except Exception:
                                    pass
                            except Exception:
                                pass
                            logger.warning("Decision persisted to Redis DLQ (will retry later)")
                        except (RedisUnavailable, RedisOpFailed) as re:
                            logger.exception("failed to push to redis DLQ, falling back to in-memory: %s", re)
                            async with self._dlq_lock:
                                self._persist_dlq.append(entry)
                    else:
                        async with self._dlq_lock:
                            self._persist_dlq.append(entry)
                            logger.warning("Decision persisted to in-memory DLQ (will retry later)")
                            try:
                                dlq_size.set(len(self._persist_dlq))
                            except Exception:
                                pass
                except Exception as dlq_e:
                    logger.error("Failed to enqueue to in-memory DLQ: %s", dlq_e)
                dec_id = None
        else:
            decisions_processed_total.labels(result="skipped_persist").inc()

        # channel selection
        if channels is None:
            routed = self._get_routing_for_decision(d)
        else:
            routed = channels

        # quiet hours check
        if self._is_quiet_hours() and not d.get("urgent", False):
            results = {ch: {"ok": False, "skipped": True, "reason": "quiet_hours"} for ch in routed}
            return {"id": dec_id, "skipped": skipped, "notify_results": results}

        # concurrent notify
        tasks = []
        for ch in routed:
            notifier = self.notifiers.get(ch)
            if not notifier:
                continue
            tasks.append(notifier.notify(d, decision_id=dec_id))
        notify_results = {}
        if tasks and not skipped:
            # Use return_exceptions=True so one notifier failure doesn't cancel others
            res_list = await asyncio.gather(*tasks, return_exceptions=True)
            for ch, r in zip(routed, res_list):
                if isinstance(r, Exception):
                    # Normalize exception into a notifier result dict, preserve exception text
                    logger.error(f"Notifier {ch} raised: {r}")
                    notify_results[ch] = {"ok": False, "error": str(r)}
                else:
                    notify_results[ch] = r
        else:
            for ch in routed:
                notify_results[ch] = {"ok": False, "skipped": True}

        return {"id": dec_id, "skipped": skipped, "notify_results": notify_results}

    async def notify(self, channel: str, payload: Dict[str, Any], ctx: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Adapter to route a single notification through configured notifiers.

        Delegates to existing notifier infrastructure; preserves existing behavior.
        """
        notifier = self.notifiers.get(channel)
        if not notifier:
            return {"ok": False, "error": "unconfigured"}
        try:
            decision_id = None
            if isinstance(ctx, dict):
                decision_id = ctx.get("decision_id") or ctx.get("id")
            res = await notifier.notify(payload, decision_id=decision_id)
            return res
        except Exception as e:
            logger.exception("notify adapter error: %s", e)
            return {"ok": False, "error": str(e)}

    async def publish_to_dlq(self, payload: Dict[str, Any]) -> bool:
        """Adapter to publish a payload to the orchestrator's DLQ fallback.

        This will use Redis DLQ if configured and available, otherwise append to the
        in-memory DLQ. Returns True on success, False otherwise.
        """
        try:
            entry = {"decision": payload, "error": "published_via_adapter", "ts": int(time.time() * 1000), "attempts": 0, "next_attempt_ts": 0.0}
            if _cfg.REDIS_DLQ_ENABLED and getattr(self, "_redis", None) is not None:
                try:
                    from utils.redis_wrapper import RedisUnavailable, RedisOpFailed
                    await redis_op(self, lambda r, key, v: r.rpush(key, v), _cfg.REDIS_DLQ_KEY, json.dumps(entry))
                    try:
                        llen = await redis_op(self, lambda r, key: r.llen(key), _cfg.REDIS_DLQ_KEY)
                        try:
                            dlq_size.set(llen)
                        except Exception:
                            pass
                    except Exception:
                        pass
                    return True
                except Exception:
                    # fallthrough to in-memory fallback
                    logger.exception("redis dlq push failed, falling back to in-memory")
            async with self._dlq_lock:
                self._persist_dlq.append(entry)
                try:
                    dlq_size.set(len(self._persist_dlq))
                except Exception:
                    pass
            return True
        except Exception as e:
            logger.exception("publish_to_dlq adapter error: %s", e)
            return False

    async def run_from_queue(self, queue: asyncio.Queue, stop_event: Optional[asyncio.Event] = None) -> None:
        while True:
            if stop_event and stop_event.is_set():
                break
            try:
                decision = await asyncio.wait_for(queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            try:
                # Policy gate: allow pre-reasoning hook to observe incoming snapshot
                try:
                    await self.pre_reasoning_policy_check(decision, state={}, ctx=None)
                except Exception as e:
                    logger.exception("pre_reasoning_policy_check in run_from_queue failed: %s", e)

                # If the queued item contains a plan, attempt PlanExecutor integration.
                if isinstance(decision, dict) and decision.get("plan") is not None:
                    plan = decision.get("plan")
                    # Build a minimal execution context if provided
                    exec_ctx = decision.get("execution_ctx") or {
                        "signal": decision.get("signal", {}),
                        "decision": decision,
                        "corr_id": decision.get("corr_id", "no-corr"),
                    }
                    try:
                        # Delegate to existing adapter which will honor feature flags
                        pe_res = await self.execute_plan_if_enabled(plan, exec_ctx)
                        # Capture plan result in the decision for downstream processing
                        try:
                            decision["_plan_result"] = pe_res
                        except Exception:
                            pass
                        # Post-reasoning policy hook (consult PolicyStore)
                        try:
                            await self.post_reasoning_policy_check(pe_res, state={}, ctx=None)
                        except Exception as e:
                            logger.exception("post_reasoning_policy_check failed: %s", e)
                    except Exception as e:
                        logger.exception("PlanExecutor integration failed: %s", e)
                        # On failure, publish to DLQ and notify, but do not crash the loop
                        try:
                            await self.publish_to_dlq(decision)
                        except Exception:
                            logger.exception("publish_to_dlq failed while handling plan error")
                        try:
                            # best-effort notify about the failure
                            await self.notify("slack", {"error": str(e), "decision": decision}, ctx=None)
                        except Exception:
                            logger.exception("notify failed while handling plan error")

                # Continue with normal processing of the (possibly augmented) decision
                await self.process_decision(decision)
            except Exception:
                logger.exception("error processing decision")
            finally:
                try:
                    queue.task_done()
                except Exception:
                    pass

    # --- Advanced Event Orchestration Helpers ---

    async def configure_cooldown(self, event_type: str, cooldown_ms: int) -> None:
        """Configure cooldown for event type."""
        config = CooldownConfig(event_type, cooldown_ms)
        await self.orchestration_state.cooldown_manager.configure_cooldown(config)

    async def configure_session_window(
        self,
        event_type: str,
        start_hour: int = 0,
        end_hour: int = 23,
        max_events: int = 100
    ) -> None:
        """Configure session window for event type."""
        window = SessionWindow(event_type, start_hour, end_hour, max_events)
        await self.orchestration_state.cooldown_manager.configure_session_window(window)

    async def _check_event_constraints(self, event_type: str) -> Tuple[bool, Optional[str], Optional[int]]:
        """
        Check event constraints (cooldown, session window, limits).
        
        Returns:
            Tuple of (allowed, reason, next_available_ms)
        """
        # Check cooldown
        is_cooling, next_available = await self.orchestration_state.cooldown_manager.check_cooldown(
            event_type
        )
        if is_cooling:
            return False, "cooldown_active", next_available

        # Check session window
        is_active = await self.orchestration_state.cooldown_manager.check_session_window(event_type)
        if not is_active:
            return False, "outside_session_window", None

        # Check event limit
        within_limit = await self.orchestration_state.cooldown_manager.check_event_limit(event_type)
        if not within_limit:
            return False, "event_limit_exceeded", None

        return True, None, None

    async def _apply_signal_filters(
        self,
        signals: List[Any],
        event_type: str,
        context: Dict[str, Any]
    ) -> Tuple[List[Any], List[Dict[str, Any]]]:
        """
        Apply policy filters to advisory signals.
        
        Returns:
            Tuple of (filtered_signals, policy_decisions_as_dicts)
        """
        filtered_signals, policy_decisions = await self.signal_filter.apply_policies(
            signals, event_type, context
        )
        
        # Convert policy decisions to dicts for metadata
        decisions_dicts = [
            {
                "policy": d.policy_name,
                "decision": d.decision,
                "reason": d.reason,
                "signals_filtered": d.signals_filtered,
                "timestamp_ms": d.timestamp_ms
            }
            for d in policy_decisions
        ]
        
        return filtered_signals, decisions_dicts

    async def _record_event_metrics(
        self,
        status: str,
        processing_time_ms: int,
        reasoning_time_ms: int = 0
    ) -> None:
        """Record event and reasoning metrics."""
        await self.orchestration_state.record_event_processing(status, processing_time_ms)
        if reasoning_time_ms > 0:
            await self.orchestration_state.record_reasoning_call(
                success=(status == "accepted"),
                execution_time_ms=reasoning_time_ms
            )

    async def get_orchestration_metrics(self) -> Dict[str, Any]:
        """Get current orchestration metrics."""
        orch_stats = await self.orchestration_state.get_orchestration_stats()
        reasoning_stats = await self.orchestration_state.get_reasoning_stats()
        
        return {
            "orchestration": orch_stats,
            "reasoning": reasoning_stats
        }

    async def handle_event(self, event: Event) -> EventResult:
        """Event-driven control loop for stateful orchestration.

        Validates incoming events, enforces policies, routes to internal logic,
        and maintains atomic state updates. Never directly executes trades.

        Args:
            event: Event object with type, payload, timestamp, correlation_id

        Returns:
            EventResult with status, reason, decision_id, and metadata
        """
        try:
            # 1. Pre-Validation: Check event structure and system state
            if not isinstance(event, Event):
                return EventResult(status="error", reason="invalid_event_type")

            if not event.event_type or not isinstance(event.payload, dict):
                return EventResult(status="error", reason="malformed_event")

            # Check system state constraints (cooldowns, session windows)
            async with self._lock:
                now_ms = int(time.time() * 1000)

                # Check global cooldowns
                if hasattr(self, '_global_cooldown_until') and self._global_cooldown_until > now_ms:
                    return EventResult(
                        status="deferred",
                        reason="global_cooldown_active",
                        metadata={"next_attempt_ts": self._global_cooldown_until}
                    )

                # Check session windows (quiet hours, etc.)
                if self._is_quiet_hours():
                    return EventResult(status="deferred", reason="quiet_hours_active")

            # 2. Policy Check: Route based on event type and enforce constraints
            if event.event_type == "decision":
                # Route to existing decision processing
                decision = event.payload
                if not isinstance(decision, dict):
                    return EventResult(status="error", reason="invalid_decision_payload")

                # Apply pre-reasoning policy checks
                policy_result = await self.pre_reasoning_policy_check(decision)
                if policy_result.get("result") == "veto":
                    return EventResult(
                        status="rejected",
                        reason=policy_result.get("reason", "policy_veto"),
                        metadata={"policy_result": policy_result}
                    )
                elif policy_result.get("result") == "defer":
                    return EventResult(
                        status="deferred",
                        reason=policy_result.get("reason", "policy_defer"),
                        metadata={"policy_result": policy_result}
                    )

                # Stage 4: Reasoning Mode Selection
                # Select mode based on HTF bias and position state.
                # Returns early if mode selection fails.
                advisory_signals: List[AdvisorySignal] = []
                advisory_errors: List[str] = []
                selected_reasoning_mode: Optional[ReasoningMode] = None
                
                if self.reasoning_manager is not None:
                    # Attempt mode selection
                    mode_result = self._select_reasoning_mode(decision, event)
                    if isinstance(mode_result, EventResult):
                        # Mode selection failed; return rejection
                        return mode_result
                    
                    selected_reasoning_mode = mode_result
                    logger.info(
                        "Stage 4 Mode Selected: %s (decision: %s)",
                        selected_reasoning_mode,
                        decision.get("id", event.correlation_id)
                    )
                    
                    # Guard: reasoning only with valid mode
                    try:
                        decision_id = decision.get("id", event.correlation_id)
                        plan_id = decision.get("plan", {}).get("id") if isinstance(decision.get("plan"), dict) else None
                        
                        # Invoke reasoning manager
                        advisory_signals = await self.reasoning_manager.reason(
                            decision_id=decision_id,
                            event_payload=decision,
                            execution_context={
                                "decision_id": decision_id,
                                "timestamp": int(time.time() * 1000),
                                "event_type": event.event_type,
                                "correlation_id": event.correlation_id,
                                "reasoning_mode": selected_reasoning_mode
                            },
                            reasoning_mode=selected_reasoning_mode,
                            plan_id=plan_id
                        )
                    except Exception as e:
                        advisory_errors.append(f"reasoning_exception: {str(e)}")
                        logger.warning("Reasoning exception (non-fatal): %s", e)

                # 3. Plan Execution: If decision contains plan, execute it
                plan_result = None
                if "plan" in decision and "execution_context" in decision:
                    try:
                        plan_result = await self.execute_plan_if_enabled(
                            decision["plan"], decision["execution_context"]
                        )
                        # Post-validation: Check execution constraints
                        if isinstance(plan_result, dict) and plan_result.get("status") == "failure":
                            return EventResult(
                                status="rejected",
                                reason="plan_execution_failed",
                                metadata={
                                    "plan_result": plan_result,
                                    "advisory_signals": [
                                        {
                                            "decision_id": s.decision_id,
                                            "signal_type": s.signal_type,
                                            "payload": s.payload,
                                            "confidence": s.confidence
                                        }
                                        for s in advisory_signals
                                    ],
                                    "advisory_errors": advisory_errors
                                }
                            )
                    except Exception as e:
                        advisory_errors.append(f"plan_execution_error: {str(e)}")

                # 4. Process the decision through normal flow
                try:
                    await self.process_decision(decision)
                    decision_id = decision.get("id") or event.correlation_id
                    return EventResult(
                        status="accepted",
                        decision_id=decision_id,
                        metadata={
                            "plan_result": plan_result,
                            "advisory_signals": [
                                {
                                    "decision_id": s.decision_id,
                                    "signal_type": s.signal_type,
                                    "payload": s.payload,
                                    "confidence": s.confidence,
                                    "reasoning_mode": s.reasoning_mode,
                                    "error": s.error
                                }
                                for s in advisory_signals
                            ],
                            "advisory_errors": advisory_errors
                        }
                    )
                except Exception as e:
                    return EventResult(
                        status="error",
                        reason=f"decision_processing_error: {str(e)}"
                    )

            elif event.event_type == "plan_execution":
                # Direct plan execution request
                if "plan" not in event.payload or "execution_context" not in event.payload:
                    return EventResult(status="error", reason="missing_plan_or_context")

                try:
                    plan_result = await self.execute_plan_if_enabled(
                        event.payload["plan"], event.payload["execution_context"]
                    )
                    if isinstance(plan_result, dict) and plan_result.get("status") == "failure":
                        return EventResult(
                            status="rejected",
                            reason="plan_execution_failed",
                            metadata={"plan_result": plan_result}
                        )
                    return EventResult(
                        status="accepted",
                        decision_id=event.correlation_id,
                        metadata={"plan_result": plan_result}
                    )
                except Exception as e:
                    return EventResult(
                        status="error",
                        reason=f"plan_execution_error: {str(e)}"
                    )

            else:
                # Unknown event type
                return EventResult(status="rejected", reason="unsupported_event_type")

        except Exception as e:
            # 5. State Update: Record any errors atomically
            async with self._lock:
                try:
                    if not hasattr(self, '_event_errors'):
                        self._event_errors = []
                    self._event_errors.append({
                        "ts": int(time.time() * 1000),
                        "event_type": getattr(event, 'event_type', 'unknown'),
                        "correlation_id": getattr(event, 'correlation_id', 'unknown'),
                        "error": str(e)
                    })
                    # Keep only recent errors
                    if len(self._event_errors) > 100:
                        self._event_errors = self._event_errors[-100:]
                except Exception:
                    pass  # Never fail on error recording

            return EventResult(status="error", reason=f"unexpected_error: {str(e)}")

    async def close(self):
        # stop DLQ retry task
        if self._dlq_task:
            try:
                self._dlq_task.cancel()
                await self._dlq_task
            except asyncio.CancelledError:
                pass
            except Exception:
                logger.exception("error stopping DLQ task")
        # close redis client if present
        if self._redis:
            try:
                # use wrapper to close gracefully
                try:
                    await redis_op(self, lambda r: r.close())
                except Exception:
                    # close is best-effort; swallow errors but log below
                    pass
            except Exception:
                logger.exception("error closing redis client")
        if self.engine:
            await self.engine.dispose()

    async def _dlq_retry_loop(self) -> None:
        """Background loop that periodically attempts to re-persist DLQ entries.

        This loop is intentionally additive and non-blocking when DLQ is empty.
        """
        poll_interval = max(0.5, float(get_settings().DLQ_POLL_INTERVAL_SECONDS or 5))
        while True:
            try:
                await self._dlq_retry_once()
            except Exception:
                logger.exception("error during DLQ retry iteration")
            try:
                await asyncio.sleep(poll_interval)
            except asyncio.CancelledError:
                break

    async def _ensure_redis(self, max_attempts: Optional[int] = None, base_delay: Optional[float] = None):
        """Ensure self._redis is connected, with exponential backoff on failures.

        This sets `self._redis` to an aioredis client or None on persistent failure.
        """
        # Attempt to import redis.asyncio dynamically so tests can monkeypatch sys.modules
        try:
            import importlib

            local_aioredis = importlib.import_module("redis.asyncio")
        except Exception:
            # fallback to module-level aioredis captured at import time
            local_aioredis = aioredis
        if local_aioredis is None:
            self._redis = None
            return

        # load defaults from config when not provided
        cfg = get_settings()
        max_attempts = int(max_attempts or cfg.REDIS_RECONNECT_MAX_ATTEMPTS)
        base_delay = float(base_delay or cfg.REDIS_RECONNECT_BASE_DELAY)
        max_delay = float(cfg.REDIS_RECONNECT_MAX_DELAY)
        jitter_ms = int(cfg.REDIS_RECONNECT_JITTER_MS)
        cooldown = float(cfg.REDIS_CIRCUIT_COOLDOWN_SECONDS)

        now = time.time()
        if self._redis_circuit_open_until and now < self._redis_circuit_open_until:
            logger.warning("redis circuit open until %s, skipping reconnect attempts", self._redis_circuit_open_until)
            self._redis = None
            return

        attempts = 0
        while attempts < max_attempts:
            try:
                self._redis = local_aioredis.from_url(_cfg.REDIS_URL)
                # test connection with ping
                try:
                    pong = await self._redis.ping()
                    if pong:
                        # reset failure counter on success
                        self._redis_failure_count = 0
                        self._redis_circuit_open_until = 0.0
                        return
                except Exception:
                    # ping failed, close and retry
                    try:
                        await self._redis.close()
                    except Exception:
                        pass
                    self._redis = None
                    raise
            except Exception:
                attempts += 1
                self._redis_failure_count += 1
                try:
                    redis_reconnect_attempts.inc()
                except Exception:
                    pass
                # exponential backoff + jitter
                delay = min(max_delay, base_delay * (2 ** (attempts - 1)))
                # jitter
                jitter = (jitter_ms / 1000.0) * (0.5 - (time.time() % 1))
                delay = max(0.0, delay + jitter)
                logger.warning("redis connect attempt %d failed, retrying in %.1fs (jitter %.3f)", attempts, delay, jitter)
                await asyncio.sleep(delay)

        # if we exhausted attempts, open circuit for cooldown
        self._redis = None
        self._redis_circuit_open_until = time.time() + cooldown
        logger.error("could not establish redis connection for DLQ after %d attempts, circuit open for %.1fs", max_attempts, cooldown)

    async def _dlq_retry_once(self) -> None:
        """Process the in-memory DLQ once: try eligible entries whose next_attempt_ts <= now.

        Uses exponential backoff and removes successful entries. Entries exceeding
        max attempts will be logged and dropped.
        """
        now = time.time()
        base_delay = float(get_settings().DLQ_BASE_DELAY_SECONDS or 1.0)
        max_delay = float(get_settings().DLQ_MAX_DELAY_SECONDS or 60.0)
        max_retries = int(get_settings().DLQ_MAX_RETRIES or 5)

        entries = []
        # If redis DLQ enabled, pop one entry atomically (using LPOP) and process
        if _cfg.REDIS_DLQ_ENABLED and self._redis is not None:
            try:
                from utils.redis_wrapper import RedisUnavailable, RedisOpFailed
                # use LPOP to get oldest entry
                _raw_res = await redis_op(self, lambda r, key: r.lpop(key), _cfg.REDIS_DLQ_KEY)
                raw = _raw_res.get("value") if isinstance(_raw_res, dict) else _raw_res
                if raw is None:
                    return
                try:
                    entry = json.loads(raw)
                except Exception:
                    logger.exception("invalid DLQ entry in redis, skipping")
                    return
                entries = [entry]
            except (RedisUnavailable, RedisOpFailed):
                logger.exception("error reading from redis DLQ, falling back to in-memory for this iteration")
                async with self._dlq_lock:
                    entries = list(self._persist_dlq)
        else:
            # copy indices to avoid mutation during iteration
            async with self._dlq_lock:
                entries = list(self._persist_dlq)

        if not entries:
            return

        for idx, entry in enumerate(entries):
            try:
                attempts = int(entry.get("attempts", 0))
                next_ts = float(entry.get("next_attempt_ts", 0.0) or 0.0)
                if next_ts > now:
                    continue

                decision = entry.get("decision")
                # choose session arg like primary flow
                session_arg = self._sessionmaker if self._sessionmaker is not None else self.engine
                try:
                    dec_id = await insert_decision(session_arg, symbol=decision.get("symbol"), decision_text=json.dumps(decision), raw=decision, bias=decision.get("bias","neutral"), confidence=float(decision.get("confidence",0.0)), recommendation=decision.get("recommendation"), repair_used=bool(decision.get("repair_used")), fallback_used=bool(decision.get("fallback_used")), duration_ms=int(decision.get("duration_ms",0)), ts_ms=int(decision.get("timestamp_ms", int(time.time()*1000))))
                    logger.info("DLQ retry success for symbol=%s attempts=%d dec_id=%s", decision.get("symbol"), attempts, dec_id)
                    # if using redis we already popped the entry; nothing else to do
                    if _cfg.REDIS_DLQ_ENABLED and self._redis is not None:
                        # success: already removed via LPOP
                        pass
                    else:
                        # remove entry from in-memory list
                        async with self._dlq_lock:
                            try:
                                self._persist_dlq.remove(entry)
                            except ValueError:
                                pass
                    continue
                except Exception as e:
                    attempts += 1
                    # compute next attempt ts with exponential backoff
                    delay = min(max_delay, base_delay * (2 ** (attempts - 1)))
                    next_attempt = now + delay
                    entry["attempts"] = attempts
                    entry["error"] = str(e)
                    entry["next_attempt_ts"] = next_attempt
                    if _cfg.REDIS_DLQ_ENABLED and self._redis is not None:
                        # push back to redis with updated metadata (RPUSH)
                        try:
                            await redis_op(self, lambda r, key, v: r.rpush(key, v), _cfg.REDIS_DLQ_KEY, json.dumps(entry))
                        except Exception:
                            logger.exception("failed to push failed entry back to redis DLQ")
                    else:
                        async with self._dlq_lock:
                            # update stored entry (if still present)
                            for i, stored in enumerate(self._persist_dlq):
                                if stored is entry or stored.get("ts") == entry.get("ts"):
                                    self._persist_dlq[i] = entry
                                    break
                        try:
                            dlq_retries_total.inc()
                        except Exception:
                            pass
                    if attempts >= max_retries:
                        logger.error("DLQ entry exceeded max retries and will be dropped symbol=%s attempts=%d error=%s", decision.get("symbol"), attempts, str(e))
                        if _cfg.REDIS_DLQ_ENABLED and self._redis is not None:
                            # entry already popped; nothing to remove
                            pass
                        else:
                            async with self._dlq_lock:
                                try:
                                    self._persist_dlq.remove(entry)
                                except ValueError:
                                    pass
                    else:
                        logger.warning("DLQ retry failed for symbol=%s attempts=%d next_attempt_in=%.1fs error=%s", decision.get("symbol"), attempts, delay, str(e))
            except Exception:
                logger.exception("unexpected error processing DLQ entry")

