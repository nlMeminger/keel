import logging
import re

import app.database as database
from app.admin.models import LogEntry

# Heuristic safety net on top of call sites already being expected to mask tokens
# themselves (CLAUDE.md: "mask to the last 4-5 chars") — any run of 20+ token-shaped
# characters (covers JWTs, hex/base64 hashes, API keys) gets redacted before a log line
# ever reaches storage.
_SECRET_LIKE = re.compile(r"[A-Za-z0-9_\-\.]{20,}")


def mask_secrets(message: str) -> str:
    return _SECRET_LIKE.sub(lambda m: f"...{m.group(0)[-4:]}", message)


class DatabaseLogHandler(logging.Handler):
    """Persists qualifying records as `LogEntry` rows for `GET /admin/logs` to read.

    Resolves `database.SessionLocal` via module attribute (not a plain import) so it
    routes to the test database during tests, same reason app.sync.tasks does (conftest's
    `_reset_job_database_session` patches the module attribute, not the name itself).
    """

    def emit(self, record: logging.LogRecord) -> None:
        try:
            db = database.SessionLocal()
            try:
                db.add(
                    LogEntry(
                        level=record.levelname,
                        logger_name=record.name,
                        message=mask_secrets(record.getMessage()),
                    )
                )
                db.commit()
            finally:
                db.close()
        except Exception:
            self.handleError(record)


def install_log_capture() -> None:
    """Call once at app startup. Attached to the "app" logger (every app.* module logs
    under that hierarchy) rather than the root logger, so it never captures — and never
    risks recursing on — SQLAlchemy's own engine/pool logging from the handler's own writes.
    """
    handler = DatabaseLogHandler()
    handler.setLevel(logging.WARNING)
    logging.getLogger("app").addHandler(handler)
