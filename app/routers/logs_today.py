import os
from datetime import datetime, timezone
from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import FileResponse
from app.core.config import settings

router = APIRouter(prefix="/logs", tags=["logs"])


def get_today_log_path() -> str:
    today_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    daily_dir = os.path.join(os.path.dirname(settings.LOG_FILE_PATH), today_str)
    return os.path.abspath(os.path.join(daily_dir, os.path.basename(settings.LOG_FILE_PATH)))


@router.get("/today", response_class=FileResponse)
async def get_today_log(inline: bool = Query(False, description="View inline instead of download")):
    log_path = get_today_log_path()
    if not os.path.exists(log_path):
        raise HTTPException(status_code=404, detail="Today's log file not found")

    filename = os.path.basename(log_path)
    disposition = "inline" if inline else "attachment"

    return FileResponse(
        path=log_path,
        media_type="text/plain",
        filename=filename,
        headers={"Content-Disposition": f'{disposition}; filename="{filename}"'},
    )
