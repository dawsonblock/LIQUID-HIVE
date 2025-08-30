from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional

import urllib.request as req
import urllib.error as err


class LoRAXClient:
    """Minimal HTTP client for a LoRAX server.

    Settings expected (if present):
      - settings.lorax_endpoint (e.g., http://lorax:8080)
      - settings.lorax_api_key (optional)
    """

    def __init__(self, base_url: Optional[str], api_key: Optional[str] = None) -> None:
        self.base = base_url.rstrip("/") if base_url else None
        self.api_key = api_key

    def _headers(self) -> Dict[str, str]:
        h = {"Content-Type": "application/json"}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    def online_sft(self, prompt: str, response: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if not self.base:
            return {"status": "disabled"}
        url = f"{self.base}/v1/lorax/online_sft"
        body = json.dumps({"prompt": prompt, "response": response, "metadata": metadata or {}}).encode()
        try:
            r = req.Request(url, data=body, headers=self._headers(), method="POST")
            with req.urlopen(r, timeout=30) as resp:
                return json.loads(resp.read().decode())
        except err.HTTPError as e:
            return {"status": "error", "detail": f"HTTP {e.code}: {e.reason}"}
        except Exception as e:  # pragma: no cover
            return {"status": "error", "detail": str(e)}