import os
import re
import asyncio
from datetime import datetime, timezone
from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import PlainTextResponse, JSONResponse, StreamingResponse
from app.core.config import settings

router = APIRouter(prefix="/logs", tags=["logs"])

COLOR_MAP = {
    "ERROR": "\033[91m",
    "WARNING": "\033[93m",
    "INFO": "\033[92m",
    "DEBUG": "\033[94m",
    "RESET": "\033[0m",
}


def get_today_log_path() -> str:
    today_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    daily_dir = os.path.join(os.path.dirname(settings.LOG_FILE_PATH), today_str)
    return os.path.abspath(os.path.join(daily_dir, os.path.basename(settings.LOG_FILE_PATH)))


def tail_file(path: str, lines: int = 100) -> list[str]:
    if not os.path.exists(path):
        raise FileNotFoundError("Today's log file not found")

    with open(path, "rb") as f:
        f.seek(0, os.SEEK_END)
        end = f.tell()
        buffer = bytearray()
        line_count = 0
        while end > 0 and line_count <= lines:
            chunk_size = min(1024, end)
            end -= chunk_size
            f.seek(end)
            buffer.extend(f.read(chunk_size))
            line_count = buffer.count(b"\n")
        text = buffer.decode(errors="ignore").splitlines()
        return text[-lines:] if len(text) > lines else text


def highlight_line(line: str) -> str:
    for level, color in COLOR_MAP.items():
        if level == "RESET":
            continue
        if re.search(rf"\b{level}\b", line, re.IGNORECASE):
            return f"{color}{line}{COLOR_MAP['RESET']}"
    return line


async def log_streamer(path: str, poll_interval: float = 1.0, keywords: list[str] | None = None, colorize: bool = False):
    # Yield recent lines first
    for line in tail_file(path, 10):
        yield f"data: {line}\n\n"

    # Then follow new ones
    with open(path, "r", encoding="utf-8") as f:
        f.seek(0, os.SEEK_END)
        while True:
            line = f.readline()
            if not line:
                await asyncio.sleep(poll_interval)
                continue
            if keywords and not any(k.lower() in line.lower() for k in keywords):
                continue
            yield f"data: {line.strip()}\n\n"


@router.get("/tail")
async def get_log_tail(
    lines: int = Query(100, ge=1, le=1000),
    as_json: bool = Query(False),
    stream: bool = Query(False),
    filter: str | None = Query(None),
    color: bool = Query(False),
):
    log_path = get_today_log_path()
    if not os.path.exists(log_path):
        raise HTTPException(status_code=404, detail="Today's log file not found")

    keywords = [k.strip() for k in filter.split(",")] if filter else None

    if stream:
        return StreamingResponse(
            log_streamer(log_path, keywords=keywords, colorize=color),
            media_type="text/event-stream",
        )

    last_lines = tail_file(log_path, lines)
    if keywords:
        last_lines = [l for l in last_lines if any(k.lower() in l.lower() for k in keywords)]
    if color:
        last_lines = [highlight_line(l) for l in last_lines]

    if as_json:
        import json
        parsed = []
        for l in last_lines:
            try:
                parsed.append(json.loads(l))
            except json.JSONDecodeError:
                parsed.append({"raw": l})
        return JSONResponse(content=parsed)

    return PlainTextResponse("\n".join(last_lines))
