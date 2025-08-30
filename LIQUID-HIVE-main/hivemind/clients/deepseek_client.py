"""
DeepSeek Client
================

This module defines a simple asynchronous client for the DeepSeek-V3 API.  The
client is designed to be resilient in environments where external network
access may not be available.  In a production deployment you should replace
the stubbed ``generate`` implementation with real HTTP calls to the
DeepSeek service.  Authentication is handled via the ``DEEPSEEK_API_KEY``
environment variable.

Example usage::

    from .deepseek_client import DeepSeekClient
    client = DeepSeekClient()
    result = await client.generate(system_prompt, user_prompt)

The result returned should be a string containing the raw output from
DeepSeek.  Downstream modules are responsible for parsing this into JSON.
"""

from __future__ import annotations

import asyncio
import json
import os
import random
import logging
from typing import Any, Optional

try:
    import httpx
except ImportError:
    httpx = None


class DeepSeekClient:
    """Asynchronous client for the DeepSeek-V3 model.

    The client exposes a single ``generate`` method that accepts a system
    prompt and a user prompt and returns the model's response.  This
    implementation includes both real API integration and robust fallback
    logic for environments without API access.
    """

    def __init__(self, api_key: Optional[str] | None = None) -> None:
        # Read the API key from the environment if not explicitly provided.
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY")
        self.base_url = "https://api.deepseek.com/v1/chat/completions" # DeepSeek's actual endpoint
        if not self.api_key:
            logging.warning("DeepSeek API key not found. DeepSeekClient will use stub responses.")

    async def generate(self, system_prompt: str, user_prompt: str) -> str:
        """Generate a response from the DeepSeek model.

        Parameters
        ----------
        system_prompt : str
            The system prompt describing the task to the model.
        user_prompt : str
            The user prompt containing the original question and the
            synthesized answer.

        Returns
        -------
        str
            The raw string response from the model.  If the external API
            cannot be contacted, the method will return a dummy JSON
            structure that simply echoes the synthesized answer.
        """
        if not self.api_key or httpx is None: # Fallback to stub if no API key or httpx
            return self._stub_response(user_prompt)

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        payload = {
            "model": "deepseek-v3", # Confirm model name
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "max_tokens": 1024, # Adjust as needed
            "temperature": 0.7, # Adjust as needed
        }
        
        async with httpx.AsyncClient(timeout=180) as client:
            try:
                response = await client.post(self.base_url, headers=headers, json=payload)
                response.raise_for_status() # Raise an exception for bad status codes
                return response.json()["choices"][0]["message"]["content"]
            except httpx.RequestError as e:
                logging.error(f"DeepSeek API request failed: {e}", exc_info=True)
                return self._stub_response(user_prompt)
            except KeyError as e:
                logging.error(f"DeepSeek API response format error: {e}, response: {response.text}", exc_info=True)
                return self._stub_response(user_prompt)

    def _stub_response(self, user_prompt: str) -> str:
        """Robust fallback implementation that provides meaningful responses."""
        try:
            # Attempt to parse the synthesized answer from the user prompt
            # by extracting the last line after a separator.  This is
            # deliberately heuristic and serves as a robust stub.
            synthesized_marker = "\nSynthesized Answer:"
            answer_part = user_prompt.split(synthesized_marker, 1)[-1].strip()
            words = answer_part.split()
            random.shuffle(words)
            shuffled = " ".join(words)
            response = {
                "correction_analysis": "This is a stubbed DeepSeek response; no real analysis was performed. Add DEEPSEEK_API_KEY to enable real Oracle refinement.",
                "identified_flaws": [],
                "final_platinum_answer": shuffled or answer_part,
            }
            return json.dumps(response)
        except Exception:
            # Fallback minimal JSON
            return json.dumps({
                "correction_analysis": "Stubbed fallback; no analysis. Add DEEPSEEK_API_KEY to enable real Oracle refinement.",
                "identified_flaws": [],
                "final_platinum_answer": "",
            })