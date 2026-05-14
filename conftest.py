"""Root pytest configuration.

Sets up structlog for test output and ensures the project root is on sys.path.
"""

from __future__ import annotations

import logging
import os

import structlog


def pytest_configure(config: object) -> None:  # noqa: ARG001
    """Configure structlog for clean test output."""
    os.environ.setdefault("CORTEX_CONTRADICTION_ENABLED", "false")
    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.WARNING),
        logger_factory=structlog.PrintLoggerFactory(),
    )
