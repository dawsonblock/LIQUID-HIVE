from __future__ import annotations

import os
import datetime as dt
from typing import Optional, Tuple

try:
    import redis as _redis
except Exception:
    _redis = None


class BudgetExceeded(Exception):
    pass


class BudgetManager:
    def __init__(self, redis_url: Optional[str] = None) -> None:
        self._r = None
        if _redis and redis_url:
            try:
                self._r = _redis.Redis.from_url(redis_url, decode_responses=True)
            except Exception:
                self._r = None
        self.max_tokens = int(os.environ.get("MAX_ORACLE_TOKENS_PER_DAY", "250000"))
        self.max_usd = float(os.environ.get("MAX_ORACLE_USD_PER_DAY", "50"))
        self.mode = os.environ.get("BUDGET_ENFORCEMENT", "hard")  # hard|warn

    def _keys(self) -> Tuple[str, str, str]:
        today = dt.datetime.utcnow().strftime("%Y%m%d")
        base = f"oracle:day:{today}:"
        return base + "tokens", base + "usd", today

    def add(self, tokens: int, usd: float) -> None:
        tkey, ukey, _ = self._keys()
        if not self._r:
            return
        pipe = self._r.pipeline()
        pipe.incrby(tkey, max(0, int(tokens)))
        pipe.incrbyfloat(ukey, max(0.0, float(usd)))
        pipe.execute()

    def get(self) -> Tuple[int, float]:
        tkey, ukey, _ = self._keys()
        if not self._r:
            return 0, 0.0
        try:
            t = int(self._r.get(tkey) or 0)
            u = float(self._r.get(ukey) or 0.0)
            return t, u
        except Exception:
            return 0, 0.0

    def check(self) -> None:
        tokens, usd = self.get()
        if tokens > self.max_tokens or usd > self.max_usd:
            if self.mode == "hard":
                raise BudgetExceeded("budget_exceeded")

    def reset(self) -> None:
        if not self._r:
            return
        tkey, ukey, _ = self._keys()
        self._r.delete(tkey)
        self._r.delete(ukey)

    def next_reset_utc(self) -> str:
        now = dt.datetime.utcnow()
        tomorrow = now + dt.timedelta(days=1)
        midnight = dt.datetime(year=tomorrow.year, month=tomorrow.month, day=tomorrow.day)
        return midnight.isoformat() + "Z"