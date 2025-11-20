import logging
import os
from datetime import datetime, timezone
from contextvars import ContextVar
from logging.handlers import RotatingFileHandler
from app.core.rich_formatter import RichJSONFormatter
from pythonjsonlogger import jsonlogger
from app.core.config import settings

try:
    import watchtower  # optional for CloudWatch
except ImportError:
    watchtower = None

# Context variable for correlation ID
correlation_id_ctx: ContextVar[str | None] = ContextVar("correlation_id", default=None)


class CorrelationIdFilter(logging.Filter):
    """Injects correlation_id into all logs."""
    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = correlation_id_ctx.get()
        return True


def _get_daily_log_dir(base_dir: str = "logs") -> str:
    """Create and return today’s log directory."""
    today_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    log_dir = os.path.join(base_dir, today_str)
    os.makedirs(log_dir, exist_ok=True)
    return log_dir


def _build_file_handler(filename: str, formatter: logging.Formatter) -> logging.Handler:
    """Builds a rotating file handler in a date-based subfolder."""
    daily_dir = _get_daily_log_dir(os.path.dirname(filename) or "logs")
    file_path = os.path.join(daily_dir, os.path.basename(filename))

    handler = RotatingFileHandler(file_path, maxBytes=10_000_000, backupCount=5, encoding="utf-8")
    handler.setFormatter(formatter)
    handler.addFilter(CorrelationIdFilter())
    return handler


# -----------------------------------------------------
# Auto-Prune Old Log Folders (older than N days)
# -----------------------------------------------------
def prune_old_log_folders(base_dir: str = "logs", days: int = 6):
    """
    Remove log folders older than N days.
    Only deletes folders with YYYYMMDD format (UTC-based).
    """
    now = datetime.now(timezone.utc)

    if not os.path.isdir(base_dir):
        return  # nothing to prune

    for name in os.listdir(base_dir):
        folder_path = os.path.join(base_dir, name)

        # Only consider folders named YYYYMMDD
        if not os.path.isdir(folder_path):
            continue
        if not name.isdigit() or len(name) != 8:
            continue

        try:
            folder_date = datetime.strptime(name, "%Y%m%d").replace(tzinfo=timezone.utc)
        except ValueError:
            continue  # skip invalid folders

        age_days = (now - folder_date).days
        if age_days > days:
            try:
                import shutil
                shutil.rmtree(folder_path)
                logging.getLogger("cleanup").info(
                    f"🗑️ Deleted old log folder {folder_path} (age {age_days} days)"
                )
            except Exception as e:
                logging.getLogger("cleanup").error(
                    f"Failed to delete log folder {folder_path}: {e}"
                )



def setup_logging():
    """Initialize JSON structured, config-driven logging."""
    for h in logging.root.handlers[:]:
        logging.root.removeHandler(h)

    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    targets = [t.strip().lower() for t in settings.LOG_TARGETS]

    formatter = jsonlogger.JsonFormatter(
        fmt="%(asctime)s %(levelname)s %(name)s %(message)s %(correlation_id)s",
        rename_fields={
            "levelname": "level",
            "asctime": "timestamp",
            "correlation_id": "correlation_id",
        },
    )

    handlers: list[logging.Handler] = []

    # Console handler
    if "console" in targets:
        console = logging.StreamHandler()
        console.addFilter(CorrelationIdFilter())
        console.setFormatter(RichJSONFormatter())
        handlers.append(console)

    # File handler
    if "file" in targets:
        handlers.append(_build_file_handler(settings.LOG_FILE_PATH, formatter))

    # CloudWatch handler
    if "cloudwatch" in targets:
        if watchtower is not None:
            cw_handler = watchtower.CloudWatchLogHandler(
                log_group=settings.AWS_CLOUDWATCH_GROUP or "AppLogs",
                stream_name=settings.AWS_CLOUDWATCH_STREAM or "main",
                create_log_group=True,
            )
            cw_handler.setFormatter(formatter)
            cw_handler.addFilter(CorrelationIdFilter())
            handlers.append(cw_handler)
        else:
            print("⚠️ CloudWatch requested but 'watchtower' not installed.")

    if not handlers:
        # Default to console if nothing configured
        console = logging.StreamHandler()
        console.setFormatter(formatter)
        console.addFilter(CorrelationIdFilter())
        handlers.append(console)

    logging.basicConfig(level=log_level, handlers=handlers, force=True)
     
    # Run auto-prune based on configuration
    try:
        prune_old_log_folders(
            base_dir=settings.LOG_DIR or "logs",
            days=settings.LOG_RETENTION_DAYS,
        )
    except Exception as e:
        logging.getLogger(__name__).error(f"Failed pruning old logs: {e}")

    logging.getLogger(__name__).info("✅ Logging initialized", extra={"targets": targets})
