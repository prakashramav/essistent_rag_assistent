import contextvars
from datetime import datetime, timezone
import json
import logging
from typing import Any, Dict

# Context variable for request correlation ID
trace_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("trace_id", default="")


class StructuredJSONFormatter(logging.Formatter):
    """
    Format log records as structured JSON with ISO timestamps,
    correlation trace IDs, and arbitrary contextual attributes.
    """

    def format(self, record: logging.LogRecord) -> str:
        log_obj: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Include trace ID if available in context
        trace_id = trace_id_ctx.get()
        if trace_id:
            log_obj["trace_id"] = trace_id

        # Include extra fields attached to log record
        extra_keys = set(record.__dict__.keys()) - {
            "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
            "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
            "created", "msecs", "relativeCreated", "thread", "threadName",
            "processName", "process", "message",
        }
        for k in extra_keys:
            val = record.__dict__[k]
            # Avoid non-serializable objects
            try:
                json.dumps(val)
                log_obj[k] = val
            except (TypeError, OverflowError):
                log_obj[k] = str(val)

        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_obj)


def setup_structured_logging():
    """Initializes JSON logging format across handlers."""
    handler = logging.StreamHandler()
    handler.setFormatter(StructuredJSONFormatter())
    
    root_logger = logging.getLogger()
    # Don't add duplicate handler if already present
    if not any(isinstance(h, logging.StreamHandler) and isinstance(h.formatter, StructuredJSONFormatter) for h in root_logger.handlers):
        root_logger.handlers = [handler]
    root_logger.setLevel(logging.INFO)
