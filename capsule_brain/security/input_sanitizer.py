"""Utilities for sanitizing and validating user provided input."""

import logging
import re
from typing import Any, Dict, List

log = logging.getLogger(__name__)


def sanitize_input(text: str) -> str:
    """Clean potentially dangerous characters and normalize whitespace.

    Args:
        text: Raw user-provided text.

    Returns:
        A sanitized string safe for further processing.
    """

    if not isinstance(text, str):
        return ""

    without_special_chars = re.sub(r"[<>()/\\\"']", "", text)
    truncated_text = without_special_chars[:2000]
    single_spaced_text = re.sub(r"\s+", " ", truncated_text)
    cleaned_text = single_spaced_text.strip()
    return cleaned_text


def validate_tool_params(params: Dict[str, Any]) -> Dict[str, Any]:
    """Validate and sanitize tool parameters.

    Args:
        params: Mapping of parameter names to their values.

    Returns:
        A new dictionary containing sanitized parameters. Supported value types
        are ``str``, ``int``, ``float``, ``bool`` and lists of these types.
        Unsupported types are skipped with a warning.
    """

    clean: Dict[str, Any] = {}
    for key, value in params.items():
        if isinstance(value, str):
            clean[key] = sanitize_input(value)
        elif isinstance(value, (int, float, bool)):
            clean[key] = value
        elif isinstance(value, list):
            sanitized_list: List[Any] = []
            for item in value[:10]:
                if isinstance(item, str):
                    sanitized_list.append(sanitize_input(item))
                elif isinstance(item, (int, float, bool)):
                    sanitized_list.append(item)
                else:
                    log.warning(
                        "Unsupported list item type for %s: %s",
                        key,
                        type(item).__name__,
                    )
            clean[key] = sanitized_list
        else:
            log.warning(
                "Unsupported parameter type for %s: %s",
                key,
                type(value).__name__,
            )

    return clean
