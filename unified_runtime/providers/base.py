from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class GenReq:
    prompt: str
    system: str = ""
    temperature: float = 0.2
    max_tokens: int = 512
    stop: Optional[List[str]] = None
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GenResp:
    text: str
    provider: str
    meta: Dict[str, Any] = field(default_factory=dict)