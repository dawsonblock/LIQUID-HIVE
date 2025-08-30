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
from typing import Any, Optional


class DeepSeekClient:
    """Asynchronous client for the DeepSeek-V3 model.

    The client exposes a single ``generate`` method that accepts a system
    prompt and a user prompt and returns the model's response.  This
    implementation intentionally avoids any hard dependency on external
    libraries such as ``openai`` or ``httpx`` so that it can run in a
    constrained environment.  In a full deployment you should replace the
    stubbed request logic with calls to the official DeepSeek API endpoint.
    """

    def __init__(self, api_key: Optional[str] | None = None) -> None:
        # Read the API key from the environment if not explicitly provided.
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY")
        # In this stub implementation we do nothing with the key, but in a
        # production system you would use it to authenticate HTTP requests.

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
        # In a real implementation, you would send an HTTP request here to
        # DeepSeek's API endpoint.  Since we cannot perform network calls in
        # this environment, we simulate a response that tries to improve
        # upon the synthesized answer by randomly shuffling words and
        # returning a structured JSON string.
        await asyncio.sleep(0.01)  # simulate network latency
        try:
            # Attempt to parse the synthesized answer from the user prompt
            # by extracting the last line after a separator.  This is
            # deliberately heuristic and serves only as a stub.
            synthesized_marker = "\nSynthesized Answer:"
            answer_part = user_prompt.split(synthesized_marker, 1)[-1].strip()
            words = answer_part.split()
            random.shuffle(words)
            shuffled = " ".join(words)
            response = {
                "correction_analysis": "This is a stubbed DeepSeek response; no real analysis was performed.",
                "identified_flaws": [],
                "final_platinum_answer": shuffled or answer_part,
            }
            return json.dumps(response)
        except Exception:
            # Fallback minimal JSON
            return json.dumps({
                "correction_analysis": "Stubbed fallback; no analysis.",
                "identified_flaws": [],
                "final_platinum_answer": "",
            })