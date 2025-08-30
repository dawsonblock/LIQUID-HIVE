from __future__ import annotations

import os
import json
import random
from typing import Optional, Dict, Any

try:
    import redis as _redis
except Exception:
    _redis = None


class AdapterDeploymentManager:
    """Minimal adapter deployment manager with canary support via Redis.

    State:
      - self.state: { role: {"active": adapter_id, "challenger": adapter_id or None} }
    Redis keys:
      - liq:canary:adapter -> challenger adapter_id
      - liq:canary:pct -> integer percent (0-100)
      - liq:canary:stats:success, liq:canary:stats:count for live stats
    """

    def __init__(self, adapters_dir: str = "/app/adapters", redis_url: Optional[str] = None) -> None:
        self.adapters_dir = adapters_dir
        self.state: Dict[str, Dict[str, Optional[str]]] = {
            "implementer": {"active": None, "challenger": None}
        }
        self._r = None
        if _redis and redis_url:
            try:
                self._r = _redis.Redis.from_url(redis_url, decode_responses=True)
            except Exception:
                self._r = None

    def get_active(self, role: str) -> Optional[str]:
        return (self.state.get(role) or {}).get("active")

    def get_challenger(self, role: str) -> Optional[str]:
        return (self.state.get(role) or {}).get("challenger")

    def set_active(self, role: str, adapter_id: Optional[str]) -> None:
        self.state.setdefault(role, {})["active"] = adapter_id

    def set_challenger(self, role: str, adapter_id: Optional[str]) -> None:
        self.state.setdefault(role, {})["challenger"] = adapter_id
        if self._r and adapter_id:
            try:
                self._r.set("liq:canary:adapter", adapter_id)
            except Exception:
                pass

    def set_traffic_pct(self, pct: int) -> None:
        pct = max(0, min(100, int(pct)))
        if self._r:
            try:
                self._r.set("liq:canary:pct", pct)
            except Exception:
                pass

    def get_traffic_pct(self) -> int:
        if self._r:
            try:
                v = self._r.get("liq:canary:pct")
                return int(v) if v is not None else 0
            except Exception:
                return 0
        return 0

    def choose_for_request(self, role: str) -> str | None:
        active = self.get_active(role)
        chall = self.get_challenger(role)
        pct = self.get_traffic_pct()
        if chall and pct > 0 and random.randint(1, 100) <= pct:
            chosen = chall
        else:
            chosen = active
        # record simple stats
        if self._r:
            try:
                self._r.incr("liq:canary:stats:count", 1)
            except Exception:
                pass
        return chosen

    def promote_challenger(self, role: str) -> Optional[str]:
        entry = self.state.setdefault(role, {})
        chall = entry.get("challenger")
        if not chall:
            return entry.get("active")
        entry["active"] = chall
        entry["challenger"] = None
        # Persist a simple champion symlink
        try:
            base = os.path.join(self.adapters_dir, "text")
            os.makedirs(base, exist_ok=True)
            champion_link = os.path.join(base, "champion")
            if os.path.islink(champion_link) or os.path.exists(champion_link):
                try:
                    os.unlink(champion_link)
                except Exception:
                    pass
            os.symlink(os.path.join(base, chall), champion_link)
        except Exception:
            pass
        return entry.get("active")

    def status(self) -> Dict[str, Any]:
        return {
            "state": self.state,
            "canary_pct": self.get_traffic_pct(),
        }