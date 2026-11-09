"""Logging configuration with secret redaction.

A filter scrubs values of secret-looking keys (password, secret, token, key, credential)
from log records so credentials never end up in log output even if a developer logs a
payload by mistake.
"""

from __future__ import annotations

import logging
import re
from typing import Any

SENSITIVE_KEY_PATTERN = re.compile(
    r"(password|passwd|secret|token|api[_-]?key|access[_-]?key|private[_-]?key|credential|"
    r"client[_-]?secret|service[_-]?account)",
    re.IGNORECASE,
)
_INLINE_PATTERN = re.compile(
    r"(?P<key>[\"']?(?:password|secret|token|access_key_id|secret_access_key|client_secret|"
    r"private_key)[\"']?\s*[:=]\s*)(?P<value>[\"']?)[^\"',\s}]+",
    re.IGNORECASE,
)
REDACTED = "***REDACTED***"


def redact(value: Any) -> Any:
    """Recursively redact sensitive keys in dicts/lists."""
    if isinstance(value, dict):
        return {
            k: (REDACTED if SENSITIVE_KEY_PATTERN.search(str(k)) else redact(v))
            for k, v in value.items()
        }
    if isinstance(value, list | tuple):
        return [redact(v) for v in value]
    return value


def redact_text(text: str) -> str:
    return _INLINE_PATTERN.sub(lambda m: f"{m.group('key')}{m.group('value')}{REDACTED}", text)


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.args, dict):
            record.args = redact(record.args)
        elif isinstance(record.args, tuple):
            record.args = tuple(redact(a) for a in record.args)
        if isinstance(record.msg, str):
            record.msg = redact_text(record.msg)
        return True


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s"))
    handler.addFilter(RedactingFilter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level.upper())
