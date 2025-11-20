# app/routers/ingest.py
from fastapi import APIRouter, UploadFile, File, Form, BackgroundTasks, Depends, HTTPException, Request
from uuid import UUID
from datetime import datetime, timezone
from sqlmodel.ext.asyncio.session import AsyncSession
from app.core.config import settings
from app.core.db import get_session
from app.core.logging_utils import get_logger, get_app_logger
from app.services.audit_service import create_audit_entry
from app.crawler.validation_pipeline import run_excel_validation_pipeline
from app.s3_utils import upload_stream_to_s3

router = APIRouter(prefix="/ingest", tags=["ingest"])


def _should_run_in_background(request: Request) -> bool:
    """Check file size (Content-Length) against threshold."""
    try:
        cl = request.headers.get("content-length")
        if not cl:
            return True
        size_bytes = int(cl)
        return size_bytes >= settings.UPLOAD_BG_THRESHOLD_MB * 1024 * 1024
    except Exception:
        return True


@router.post("/upload-and-validate")
async def upload_and_validate(
    request: Request,
    file: UploadFile = File(...),
    rules_id: UUID = Form(...),
    background_tasks: BackgroundTasks = None,
    session: AsyncSession = Depends(get_session),
):
    logger = get_logger(request)
    logger.info(f"📥 Upload request received: file={file.filename}, rules_id={rules_id}")

    if not settings.S3_BUCKET:
        logger.error("S3 bucket not configured")
        raise HTTPException(status_code=500, detail="S3 bucket not configured")

    ts = datetime.now(timezone.utc).replace(tzinfo=None).strftime("%Y%m%dT%H%M%S")
    input_key = f"{settings.INPUT_PREFIX}/{ts}_{file.filename}"

    # Upload stream directly to S3
    await upload_stream_to_s3(file.file, settings.S3_BUCKET, input_key, content_type=file.content_type)
    logger.info(f"✅ Uploaded input file to S3: {input_key}")

    # Create audit record
    audit_id = await create_audit_entry(session, file_name=input_key, rules_id=rules_id)
    logger.info(f"🧾 Created audit log entry: {audit_id}")

    # Inline or background mode?
    use_bg = _should_run_in_background(request)
    if use_bg:
        logger.info(f"📡 Running in background mode (file too large). audit_id={audit_id}")
        background_tasks.add_task(_run_validation_bg, request.app, session, audit_id, input_key, rules_id)
        return {"audit_id": audit_id, "message": "Validation started in background."}

    # Inline validation
    await run_excel_validation_pipeline(request.app, session, audit_id, input_key, rules_id)
    logger.info(f"🏁 Inline validation complete, audit_id={audit_id}")
    return {"audit_id": audit_id, "message": "Validation completed."}


async def _run_validation_bg(app, session, audit_id, input_key, rules_id):
    """Background validation handler with full logging + WebSocket progress."""
    logger = get_app_logger()
    logger.info(f"🚀 Background validation started: audit_id={audit_id}, key={input_key}")

    try:
        await run_excel_validation_pipeline(app, session, audit_id, input_key, rules_id)
        logger.info(f"🎉 Background validation completed: audit_id={audit_id}")
    except Exception as e:
        logger.exception(f"❌ Background validation failed for audit_id={audit_id}: {e}")


from app.auth.deps import user_authorize

@router.get("/read")
async def read_audit(user=Depends(user_authorize)):
    return {"user": user}
