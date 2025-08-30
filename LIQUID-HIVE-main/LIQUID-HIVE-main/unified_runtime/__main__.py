"""
Module entry point for the fusion service.

This allows the application to be run directly using ``python -m fusion``.  It
imports the FastAPI ``app`` from :mod:`fusion.server` and starts an ASGI
server using uvicorn.  The host and port can be customised via the
environment variables ``HOST`` and ``PORT``.
"""

import os
import uvicorn

from .server import app
from .logging_config import setup_logging


def main() -> None:
    """Run the FastAPI app using uvicorn.

    The host and port are read from the environment variables ``HOST`` and
    ``PORT``.  If unset they default to ``0.0.0.0`` and ``8000``.  Using
    port 8000 by default ensures compatibility with the Prometheus
    configuration bundled with this repository.
    """
    setup_logging()
    host = os.getenv("HOST", "0.0.0.0")
    # Default to port 8000 to align with Prometheus scrape configuration
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()