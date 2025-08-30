"""
LAVA Client
===========

This module provides a minimal client class for interacting with the LiquidAI
LAVA model (e.g. ``LiquidAI/LAVA-1.6B``).  The class mirrors the API of
``VLClient`` but can be extended to call a separate inference endpoint or
service optimised for visual reasoning and instruction following.

In this repository we implement a simple wrapper around ``VLClient`` to
maintain compatibility in constrained environments where the actual LAVA
model is not available.  In production you should replace the ``generate``
method with calls to your dedicated LAVA inference service.
"""
from __future__ import annotations

from typing import Any

try:
    from .vl_client import VLClient
except Exception:
    VLClient = None  # type: ignore


class LAVAClient:
    """Client for the LiquidAI LAVA multi‑modal model."""

    def __init__(self, model_id: str = "LiquidAI/LAVA-1.6B") -> None:
        # Use the VLClient as a fallback if the specialised model is not
        # accessible in this environment.  In a full deployment this
        # constructor should load or connect to the LAVA model instead.
        self.model_id = model_id
        self._fallback = None
        if VLClient is not None:
            try:
                self._fallback = VLClient(model_id)
            except Exception:
                self._fallback = None

    def generate(self, prompt: str, image: Any) -> str:
        """
        Generate a critique or answer given a prompt and an image.

        Parameters
        ----------
        prompt: str
            The system and user prompt describing the critique task.
        image: Any
            Image data to process.

        Returns
        -------
        str
            The model's generated response.  Uses the fallback VLClient when
            the specialised model is unavailable.
        """
        if self._fallback is not None:
            return self._fallback.generate(prompt, image)
        # Fallback to a dummy JSON response
        return "{}"