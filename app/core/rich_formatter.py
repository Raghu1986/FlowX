# app/core/rich_formatter.py

import json
import logging
from rich.console import Console
from rich.json import JSON
from rich.traceback import Traceback
from rich.theme import Theme


# Custom theme for log levels
LOG_THEME = Theme({
    "log.debug": "cyan",
    "log.info": "green",
    "log.warning": "yellow",
    "log.error": "red bold",
    "log.critical": "bold white on red",
})

console = Console(theme=LOG_THEME)


class RichJSONFormatter(logging.Formatter):
    """
    Rich-powered console formatter that:
      - Pretty-prints structured JSON logs
      - Adds level-based color
      - Renders tracebacks with rich formatting
    """

    def format(self, record: logging.LogRecord) -> str:
        # If it's an exception, show beautiful traceback
        if record.exc_info:
            err = Traceback.from_exception(
                record.exc_info[0],
                record.exc_info[1],
                record.exc_info[2],
                width=120,
                theme="monokai"
            )
            console.print(err)
            return ""

        # Extract the JSON payload if our structured logger passed dict in `msg`
        msg = record.getMessage()

        try:
            # Rendering actual JSON (structured log)
            json_obj = json.loads(msg)
        except Exception:
            # If message is not JSON → print raw
            console.print(f"[log.{record.levelname.lower()}]{msg}[/]")
            return ""

        # Pretty JSON output
        json_rich = JSON(json.dumps(json_obj, indent=2))

        console.print(f"[log.{record.levelname.lower()}]{record.levelname}[/log.{record.levelname.lower()}]")
        console.print(json_rich)

        return ""
