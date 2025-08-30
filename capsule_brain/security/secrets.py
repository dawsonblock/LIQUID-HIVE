"""Utility helpers for retrieving and validating secrets."""

import logging
import os
import re


log = logging.getLogger(__name__)

# Compile once at import time to avoid repeated work in ``validate_api_key``
API_KEY_PATTERN = re.compile(r"^[A-Za-z0-9]{10,}$")


class SecretNotFoundError(RuntimeError):
    """Raised when a required secret is missing."""


class InvalidAPIKeyError(ValueError):
    """Raised when an API key fails validation."""


class SecretManager:
    """Centralized access and validation for secret values."""

    @staticmethod
    def get_secret(key: str, default: str | None = None) -> str | None:
        """Retrieve an optional secret from the environment.

        Args:
            key: Name of the environment variable to look up.
            default: Value to return if the variable is not set.

        Returns:
            The secret value or ``default`` if the variable is missing.
        """
        value = os.getenv(key, default)
        if value is None:
            if default is None:
                log.warning("Secret %s not found", key)
            else:
                log.info("Secret %s not set; using default", key)
        else:
            log.info("Secret %s retrieved", key)
        return value

    @staticmethod
    def get_required_secret(key: str) -> str:
        """Retrieve a required secret from the environment.

        Args:
            key: Name of the environment variable to look up.

        Returns:
            The secret value associated with ``key``.

        Raises:
            SecretNotFoundError: If the environment variable is not set.
        """
        value = os.getenv(key)
        if value is None:
            log.error("Required secret %s not found", key)
            raise SecretNotFoundError(f"Required secret {key} not found")
        log.info("Required secret %s retrieved", key)
        return value

    @staticmethod
    def validate_api_key(api_key: str) -> None:
        """Validate that an API key meets basic format requirements.

        The key must be at least 10 characters long and contain only
        alphanumeric characters.

        Args:
            api_key: API key to validate.

        Returns:
            ``None`` if the key is valid.

        Raises:
            InvalidAPIKeyError: If the key is missing or does not match the
            required format.
        """
        if not api_key:
            log.error("API key validation failed: no key provided")
            raise InvalidAPIKeyError("API key must be provided")
        if not API_KEY_PATTERN.fullmatch(api_key):
            log.error("API key validation failed: invalid format")
            raise InvalidAPIKeyError(
                "API key must be at least 10 alphanumeric characters"
            )
        log.info("API key validation succeeded")
