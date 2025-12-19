import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class ExecutionContext:
    orch: Any  # orchestrator instance
    signal: Dict[str, Any]
    decision: Dict[str, Any]
    corr_id: str
    results: Dict[str, Any] = field(default_factory=dict)


class PlanExecutor:
    def __init__(self, orch: Any, max_concurrency: int = 4):
        self.orch = orch
        self.semaphore = asyncio.Semaphore(max_concurrency)

    async def run_plan(self, plan: Dict[str, Any], ctx: ExecutionContext) -> Dict[str, Any]:
        # Validate plan shape
        if not isinstance(plan, dict):
            raise ValueError("plan must be a dict")
        if "start" not in plan or not isinstance(plan["start"], str):
            raise ValueError("plan must contain a 'start' string")
        if "steps" not in plan or not isinstance(plan["steps"], dict):
            raise ValueError("plan must contain a 'steps' dict mapping step_id -> step")

        steps = plan["steps"]
        current = plan["start"]

        while current:
            if current not in steps:
                logger.error("plan step '%s' not found in plan steps", current)
                break
            step = steps[current]
            step_id = current
            typ = step.get("type", "unknown")
            logger.debug("Starting step '%s' (type=%s)", step_id, typ)

            max_retries = int(step.get("retries", 1))
            attempt = 0
            last_exc = None
            succeeded = False
            while attempt < max_retries:
                attempt += 1
                try:
                    async with self.semaphore:
                        result = await self._run_step(step, ctx)
                    ctx.results[step_id] = result
                    logger.debug("Step '%s' finished successfully", step_id)
                    next_step = step.get("on_success")
                    logger.debug("Transition on_success -> %s", next_step)
                    current = next_step
                    succeeded = True
                    break
                except Exception as exc:
                    last_exc = exc
                    logger.exception("Step '%s' failed on attempt %d: %s", step_id, attempt, exc)
                    if attempt < max_retries:
                        logger.debug("Retrying step '%s' (attempt %d/%d)", step_id, attempt + 1, max_retries)
                        await asyncio.sleep(float(step.get("retry_delay_s", 0)))
                        continue
                    # exhausted retries
                    fail_next = step.get("on_failure")
                    logger.debug("Transition on_failure -> %s", fail_next)
                    if fail_next:
                        current = fail_next
                        succeeded = False
                        break
                    else:
                        await self._handle_failure_to_dlq(ctx, step, exc)
                        # end plan execution
                        return ctx.results

            # safety: if the step neither succeeded nor set current, break
            if not succeeded and not current:
                break

        return ctx.results

    async def _run_step(self, step: Dict[str, Any], ctx: ExecutionContext) -> Any:
        typ = step.get("type")
        spec = step.get("spec", {}) or {}

        if typ == "call_ai":
            prompt = spec["prompt"]
            timeout = float(step.get("timeout_s", 30))
            # orchestrator is expected to expose reasoner.call(prompt, signal, decision)
            coro = self.orch.reasoner.call(prompt, ctx.signal, ctx.decision)
            return await asyncio.wait_for(coro, timeout=timeout)

        elif typ == "eval":
            expr = spec.get("expr", "")
            # Very conservative safety check
            import re

            if "__" in expr:
                raise ValueError("Unsafe eval expression")
            if re.search(r"[^A-Za-z0-9_ .\[\]\(\)'\"<>=!&|]", expr):
                raise ValueError("Unsafe eval expression")
            # TODO: Replace eval with sandboxed expression interpreter in next iteration
            return eval(expr, {"__builtins__": {}}, {"results": ctx.results, "ctx": ctx})

        elif typ == "notify":
            channel = spec["channel"]
            payload_template = spec["payload"]
            flat = flatten_results(ctx.results)
            try:
                rendered = payload_template.format(**flat)
            except Exception as e:
                raise RuntimeError(f"failed to render payload: {e}")
            # orch.notify returns a coroutine
            coro = self.orch.notify(channel, rendered, ctx)
            if asyncio.iscoroutine(coro):
                await coro
            return {"ok": True}

        elif typ == "wait":
            secs = float(spec.get("seconds", 1))
            await asyncio.sleep(secs)
            return {"waited": True}

        else:
            raise ValueError(f"unknown step type: {typ}")

    async def _handle_failure_to_dlq(self, ctx: ExecutionContext, step: Dict[str, Any], exc: Exception):
        payload = {
            "corr_id": ctx.corr_id,
            "signal": ctx.signal,
            "decision": ctx.decision,
            "failed_step": step,
            "error": str(exc),
        }
        try:
            publish = getattr(self.orch, "publish_to_dlq", None)
            if callable(publish):
                maybe = publish(payload)
                if asyncio.iscoroutine(maybe):
                    await maybe
                logger.warning("Published plan failure to DLQ via orch.publish_to_dlq")
                return
            else:
                logger.warning("No publish_to_dlq on orch, DLQ not sent. Payload: %s", payload)
        except Exception:
            logger.exception("Failed to publish plan failure to DLQ")


def flatten_results(results: Dict[str, Any]) -> Dict[str, Any]:
    flat: Dict[str, Any] = {}

    def _recurse(prefix: str, obj: Any):
        if isinstance(obj, dict):
            for k, v in obj.items():
                new_prefix = f"{prefix}.{k}" if prefix else str(k)
                _recurse(new_prefix, v)
        else:
            # support both dot and bracket styles for formatting
            key_dot = f"{prefix}"
            # dot form: results.s1.key
            flat_key1 = f"{key_dot}"
            if not flat_key1.startswith('results'):
                flat_key1 = f"results.{flat_key1}"
            flat[flat_key1] = obj
            # bracket form: results[s1][key]
            bracket = key_dot.replace('.', '][')
            flat[f"results[{bracket}]"] = obj

    for step_id, val in results.items():
        _recurse(f"{step_id}", val)

    # also expose full results mapping for bracket-style formatting like {results[s1][key]}
    flat["results"] = results
    return flat
