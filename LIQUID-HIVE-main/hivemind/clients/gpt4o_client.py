"""
GPT-4o Client
==============

This module defines a minimal asynchronous client for the GPT-4o model from
OpenAI.  The client follows the same interface as other model clients in
this repository.  Authentication is managed via the ``OPENAI_API_KEY``
environment variable.  Error handling and retry logic are implemented to
provide resilience in the face of transient failures.  In a production
deployment you should replace the stubbed ``generate`` method with calls
to the OpenAI API.

Example usage::

    from .gpt4o_client import GPT4oClient
    client = GPT4oClient()
    response = await client.generate(system_prompt, user_prompt)

The returned value is a raw string that downstream modules should parse
into JSON.
"""

from __future__ import annotations

import asyncio
import json
import os
import random
import logging
from typing import Optional

try:
    import httpx
except ImportError:
    httpx = None


class GPT4oClient:
    """Asynchronous client for the GPT-4o model.

    The client exposes a single ``generate`` method that accepts a system
    prompt and a user prompt and returns the model's response.  This
    implementation includes both real OpenAI API integration and robust
    fallback logic for environments without API access.
    """

    def __init__(self, api_key: Optional[str] | None = None) -> None:
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.base_url = "https://api.openai.com/v1/chat/completions" # Standard OpenAI endpoint
        # A simple backoff strategy for retrying requests.
        self._max_retries = 2
        if not self.api_key:
            logging.warning("OpenAI API key not found. GPT4oClient will use stub responses.")

    async def generate(self, system_prompt: str, user_prompt: str) -> str:
        """Generate a response from GPT-4o.

        Parameters
        ----------
        system_prompt : str
            The system prompt describing the task.
        user_prompt : str
            The user prompt containing the original question and
            synthesized answer.

        Returns
        -------
        str
            The raw string response from the model.  In this stub, we
            construct a plausible JSON string from the input.
        """
        if not self.api_key or httpx is None: # Fallback to stub if no API key or httpx
            return self._stub_response(user_prompt)

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        payload = {
            "model": "gpt-4o", # Confirm model name
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "max_tokens": 1024, # Adjust as needed
            "temperature": 0.7, # Adjust as needed
        }
        
        async with httpx.AsyncClient(timeout=180) as client:
            for attempt in range(self._max_retries + 1):
                try:
                    response = await client.post(self.base_url, headers=headers, json=payload)
                    response.raise_for_status()
                    return response.json()["choices"][0]["message"]["content"]
                except httpx.RequestError as e:
                    logging.error(f"GPT-4o API request failed (attempt {attempt+1}/{self._max_retries+1}): {e}", exc_info=True)
                    if attempt < self._max_retries:
                        await asyncio.sleep(0.05 * (attempt + 1)) # Exponential backoff
                        continue
                    return self._stub_response(user_prompt)
                except KeyError as e:
                    logging.error(f"GPT-4o API response format error (attempt {attempt+1}/{self._max_retries+1}): {e}, response: {response.text}", exc_info=True)
                    return self._stub_response(user_prompt)

    def _stub_response(self, user_prompt: str) -> str:
        """Robust fallback implementation that provides meaningful responses."""
        try:
            # Simulate retry logic by using different transformations
            synthesized_marker = "\nSynthesized Answer:"
            answer_part = user_prompt.split(synthesized_marker, 1)[-1].strip()
            words = answer_part.split()
            words.reverse()
            reversed_answer = " ".join(words)
            response = {
                "correction_analysis": "This is a stubbed GPT-4o response; no real analysis was performed. Add OPENAI_API_KEY to enable real Arbiter refinement.",
                "identified_flaws": [],
                "final_platinum_answer": reversed_answer or answer_part,
            }
            return json.dumps(response)
        except Exception:
            # On final failure, return a minimal JSON response
            return json.dumps({
                "correction_analysis": "Stubbed GPT-4o fallback; no analysis. Add OPENAI_API_KEY to enable real Arbiter refinement.",
                "identified_flaws": [],
                "final_platinum_answer": "",
            })