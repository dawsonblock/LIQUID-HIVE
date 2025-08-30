from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class CostModel:
    token_price_small: float = 2e-6   # $/token (example)
    token_price_large: float = 1e-5   # $/token (example)


class ResourceEstimator:
    """Predictive cost estimator that can accept a prompt and estimate tokens and cost.

    Heuristics-only by default to avoid heavy deps. If sentence-transformers is available, could
    be extended to use it for complexity. We keep this lightweight.
    """

    def __init__(self, cost_model: Optional[CostModel] = None) -> None:
        self.cost = cost_model or CostModel()

    def _estimate_tokens(self, prompt: str) -> int:
        # Simple heuristic: 1 token ~ 4 chars, plus punctuation/structure adjustments
        base = max(1, len(prompt) // 4)
        punctuation = sum(prompt.count(c) for c in ".,;:!?()[]{}")
        lines = prompt.count("\n") + 1
        bonus = int(0.1 * punctuation + 0.05 * lines * base ** 0.3)
        return int(base + bonus)

    def estimate_cost(self, role: str = "implementer", tier: str = "auto", prompt: Optional[str] = None) -> Dict[str, Any]:
        predicted_tokens = None
        if prompt:
            predicted_tokens = self._estimate_tokens(prompt)
        # Cost for both models to aid selector
        cost_small = (predicted_tokens or 0) * self.cost.token_price_small
        cost_large = (predicted_tokens or 0) * self.cost.token_price_large
        return {
            "role": role,
            "tier": tier,
            "predicted_tokens": predicted_tokens,
            "predicted_cost_small": cost_small,
            "predicted_cost_large": cost_large,
        }