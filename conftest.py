"""Root pytest configuration.

Sets up structlog for test output and ensures the project root is on sys.path.
"""

from __future__ import annotations

import logging

import structlog


def pytest_configure(config: object) -> None:
    """Configure structlog for clean test output."""
    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.WARNING),
        logger_factory=structlog.PrintLoggerFactory(),
    )
