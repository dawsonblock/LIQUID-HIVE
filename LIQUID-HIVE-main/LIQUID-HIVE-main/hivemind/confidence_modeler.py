"""
Confidence Modeler (Trust Protocol)
===================================

A lightweight, calibratable scorer that estimates the probability an operator
would approve a proposed action based on historical approvals.

Phase 1 implementation:
- Per action_type empirical approval rate with Laplace smoothing
- Minimum sample gate and allowlist
- Shadow mode via settings.TRUSTED_AUTONOMY_ENABLED

Future work: richer features (embeddings, cost, latency), online calibration,
SHAP explanations.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any, Optional, Tuple
import time

@dataclass
class TrustPolicy:
    enabled: bool
    threshold: float
    min_samples: int
    allowlist: Tuple[str, ...]

class ConfidenceModeler:
    def __init__(self, policy: TrustPolicy) -> None:
        self.policy = policy
        # stats[action_type] = (approvals, total)
        self.stats: Dict[str, Tuple[int,int]] = {}
        self.updated_at = 0.0

    def update_from_events(self, events: list[dict[str, Any]]) -> None:
        approvals: Dict[str, Tuple[int,int]] = {}
        for ev in events:
            if ev.get("role") == "approval_feedback":
                txt = (ev.get("content") or "").upper()
                # Expect content like "APPROVED: <proposal>" or "DENIED: <proposal>"
                approved = txt.startswith("APPROVED:")
                # Try to infer action_type tag embedded in proposal, e.g., [action:doc_ingest]
                prop = txt.split(":", 1)[-1]
                action_type = "generic"
                if "[action:" in prop:
                    try:
                        action_type = prop.split("[action:",1)[1].split("]",1)[0]
                    except Exception:
                        action_type = "generic"
                a, t = approvals.get(action_type, (0,0))
                approvals[action_type] = (a + (1 if approved else 0), t + 1)
        self.stats = approvals
        self.updated_at = time.time()

    def _score(self, action_type: str) -> Tuple[float, int]:
        a, t = self.stats.get(action_type, (0,0))
        # Laplace smoothing (1,1)
        p = (a + 1) / (t + 2) if t >= 0 else 0.5
        return p, t

    def decide(self, proposal: Dict[str, Any]) -> Dict[str, Any]:
        action_type = proposal.get("action_type", "generic")
        p, n = self._score(action_type)
        bypass = (
            self.policy.enabled and
            (action_type in self.policy.allowlist if self.policy.allowlist else True) and
            n >= self.policy.min_samples and
            p >= self.policy.threshold
        )
        return {
            "score": float(p),
            "samples": int(n),
            "bypass": bool(bypass),
            "reason": f"p={p:.5f} n={n} threshold={self.policy.threshold} enabled={self.policy.enabled}",
        }

    def update_policy(self, policy: TrustPolicy) -> None:
        self.policy = policy