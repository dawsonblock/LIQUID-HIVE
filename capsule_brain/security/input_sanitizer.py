import logging
import re
from typing import Any, Dict

log = logging.getLogger(__name__)


def sanitize_input(s: str) -> str:
    """Return a sanitized string capped at 2000 chars with whitespace collapsed."""
    if not isinstance(s, str):
        return ""
    s = re.sub('[<>()/\\"\']', "", s)
    s = s[:2000]
    s = re.sub(r"\s+", " ", s).strip()
    return s


def validate_tool_params(params: Dict[str, Any]) -> Dict[str, Any]:
    """Sanitize or copy supported parameter types for safe tool invocation."""
    clean: Dict[str, Any] = {}
    for k, v in params.items():
        if isinstance(v, str):
            clean[k] = sanitize_input(v)
        elif isinstance(v, (int, float, bool)):
            clean[k] = v
        elif isinstance(v, list):
            clean[k] = [sanitize_input(str(i)) for i in v[:10]]
        else:
            log.warning(
                "Dropping unsupported param %s of type %s", k, type(v).__name__
            )
    return clean
