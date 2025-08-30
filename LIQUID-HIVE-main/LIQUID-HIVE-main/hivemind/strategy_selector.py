from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

try:
    from .resource_estimator import ResourceEstimator
except Exception:  # pragma: no cover
    ResourceEstimator = None  # type: ignore


@dataclass
class SelectorDecision:
    strategy: str
    model: str  # "small" or "large"
    chosen_model: str  # Human-friendly alias: "Courier" or "Master"
    reason: str


class StrategySelector:
    """Heuristic strategy and model selector with cost-awareness and confidence modulation.

    Inputs:
      - prompt: full prompt text
      - ctx: may include keys: operator_intent, estimated_cost (fallback), phi, planner_hints, reasoning_steps

    Behavior:
      - Predict expected token/cost via ResourceEstimator(estimate_cost(prompt=...)) if available
      - Read optional cognitive map confidence bucket from ctx.get('cognitive_map', ...) if caller adds it
      - Decide strategy among {clone_dispatch, debate, committee}
      - Decide model among {small, large}; provide alias {Courier, Master}
    """

    def __init__(self, client: Optional[Any] = None) -> None:
        self.client = client
        self.estimator = ResourceEstimator() if ResourceEstimator else None

    async def decide(self, prompt: str, ctx: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        ctx = ctx or {}
        # Predict cost/size
        predicted_tokens = None
        predicted_cost = None
        try:
            if self.estimator is not None:
                est = self.estimator.estimate_cost(role="implementer", tier="auto", prompt=prompt)
                predicted_tokens = est.get("predicted_tokens")
                predicted_cost = est.get("predicted_cost")
        except Exception:
            pass

        # Confidence modulation via cognitive map (optional)
        low_confidence = False
        try:
            cognitive = ctx.get("cognitive_map") or {}
            if isinstance(cognitive, dict):
                topic = (ctx.get("operator_intent") or "").lower()
                if topic:
                    conf = float(cognitive.get(topic, 0.75))
                    low_confidence = conf < 0.7
        except Exception:
            low_confidence = False

        # Basic heuristics
        plen = len(prompt)
        has_tools = bool(ctx.get("planner_hints"))
        complex_question = plen > 800 or (predicted_tokens and predicted_tokens > 600)

        # Model choice
        model = "large" if complex_question else "small"
        if low_confidence:
            model = "large"

        # Strategy choice
        strategy = "clone_dispatch"
        if low_confidence and complex_question:
            strategy = "committee"
        elif low_confidence or has_tools or plen > 400:
            strategy = "debate"

        human_alias = "Master" if model == "large" else "Courier"
        reason = (
            f"plen={plen}, predicted_tokens={predicted_tokens}, low_confidence={low_confidence}, "
            f"has_tools={has_tools}"
        )

        return {
            "strategy": strategy,
            "model": model,
            "chosen_model": human_alias,
            "reason": reason,
        }