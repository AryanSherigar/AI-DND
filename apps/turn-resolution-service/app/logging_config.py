"""Structlog configuration for turn-resolution-service.

Intentionally duplicated (not shared) with the identically-shaped
apps/core-api/app/logging_config.py — no shared Python package exists
between the two services, and this file is small and stable enough that
duplication beats introducing one for it. Keep both copies in sync by
hand. See docs/logging.md for the policy rationale behind the redaction
denylist and event-category split.
"""

import logging

import structlog

SERVICE_NAME = "turn-resolution-service"

FIELD_REQUEST_ID = "request_id"
FIELD_USER_ID = "user_id"
FIELD_EVENT_CATEGORY = "event_category"
EVENT_CATEGORY_OPERATIONAL = "operational"
EVENT_CATEGORY_AUDIT = "audit"

REDACTED_FIELD_NAMES: frozenset[str] = frozenset(
    {
        "token",
        "access_token",
        "refresh_token",
        "firebase_token",
        "firebase_id_token",
        "id_token",
        "authorization",
        "api_key",
        "gemini_api_key",
        "secret_key",
        "password",
        "email",
        "display_name",
        "ip",
        "ip_address",
        "prompt",
        "system_instruction",
        "narration",
        "narration_text",
        "action_text",
    }
)
REDACTION_PLACEHOLDER = "[REDACTED]"

_LEVEL_NAME_TO_NUMERIC: dict[str, int] = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


def redact_sensitive_fields(
    logger: object, method_name: str, event_dict: dict[str, object]
) -> dict[str, object]:
    """Strip known-sensitive field values before rendering, regardless of call site."""
    for key in event_dict:
        if key.lower() in REDACTED_FIELD_NAMES:
            event_dict[key] = REDACTION_PLACEHOLDER
    return event_dict


def _add_severity(
    logger: object, method_name: str, event_dict: dict[str, object]
) -> dict[str, object]:
    """Mirror `level` into GCP Cloud Logging's expected `severity` field."""
    level = event_dict.get("level")
    if isinstance(level, str):
        event_dict["severity"] = level.upper()
    return event_dict


def _add_static_fields(
    logger: object, method_name: str, event_dict: dict[str, object]
) -> dict[str, object]:
    event_dict["service"] = SERVICE_NAME
    event_dict["environment"] = _current_environment()
    return event_dict


def _current_environment() -> str:
    from app.config import settings

    return settings.environment


def configure_logging(log_level: str, log_format: str) -> None:
    """Configure structlog once, at process start, before the FastAPI app is built."""
    numeric_level = _LEVEL_NAME_TO_NUMERIC.get(log_level.upper(), logging.INFO)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            _add_severity,
            _add_static_fields,
            structlog.processors.TimeStamper(fmt="iso", utc=True, key="timestamp"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            redact_sensitive_fields,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(numeric_level),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def log_audit_event(
    logger: structlog.typing.FilteringBoundLogger, event: str, **kwargs: object
) -> None:
    """Log an info-level event tagged event_category=audit for downstream filtering."""
    logger.info(event, event_category=EVENT_CATEGORY_AUDIT, **kwargs)
