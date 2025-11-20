import json
import logging
import sys
from pythonjsonlogger import jsonlogger


# Detect if output is a terminal (color-capable)
COLOR_ENABLED = sys.stdout.isatty()


COLORS = {
    "DEBUG": "\033[36m",     # Cyan
    "INFO": "\033[32m",      # Green
    "WARNING": "\033[33m",   # Yellow
    "ERROR": "\033[31m",     # Red
    "CRITICAL": "\033[41m",  # Red background
}
RESET = "\033[0m"


class ColorizedJsonFormatter(jsonlogger.JsonFormatter):
    """
    JSON logs + optional ANSI color for console output only.
    """

    def format(self, record: logging.LogRecord) -> str:
        # Normal JSON data
        message = super().format(record)

        if not COLOR_ENABLED:
            return message  # No colors for non-TTY (files, cloudwatch)

        level = record.levelname
        color = COLORS.get(level, "")

        # Pretty indentation for readability
        try:
            json_obj = json.loads(message)
            formatted_json = json.dumps(json_obj, indent=2)
        except Exception:
            formatted_json = message

        return f"{color}{formatted_json}{RESET}"
