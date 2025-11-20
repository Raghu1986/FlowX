# app/routers/audit.py
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel.ext.asyncio.session import AsyncSession
from app.services.audit_service import get_audit_by_id
from app.s3_utils import generate_presigned_get_url
from app.core.db import get_session  # adjust if your session dep is elsewhere
from app.core.logging_utils import get_logger
import os

router = APIRouter(prefix="/audit", tags=["audit"])

@router.get("/{audit_id}/download_links")
async def get_download_links(
    request: Request,
    audit_id: str,
    expires_in: int = 1800,  # you said 1800 sec default; can be overridden via query
    session: AsyncSession = Depends(get_session),
    
):
    try:    
        logger = get_logger(request)
        logger.info("🔗 Download link request received", extra={"audit_id": audit_id})
        audit = await get_audit_by_id(session, audit_id)
        if not audit:
            logger.warning(
                    "Audit not found",
                    extra={"audit_id": audit_id},
                )
            raise HTTPException(status_code=404, detail="Audit not found.")

        if not audit.excel_s3_key and not audit.json_s3_key:
            logger.warning(
                    "No output keys recorded yet",
                    extra={"audit_id": audit_id},
                )
            raise HTTPException(status_code=409, detail="No output keys recorded yet.")

        bucket_out = 'cashdev' #os.getenv("OUTPUT_S3_BUCKET") or os.getenv("AWS_S3_BUCKET")  # choose your env var
        if not bucket_out:
            logger.error(
                    "S3 bucket not configured",
                    extra={"audit_id": audit_id},
                )
            raise HTTPException(status_code=500, detail="OUTPUT_S3_BUCKET not configured.")

        excel_url = json_url = None
        if audit.excel_s3_key:
            excel_url = await generate_presigned_get_url(bucket_out, audit.excel_s3_key, expires_in)
            logger.info(
                    "Generated Excel presigned URL",
                    extra={
                        "audit_id": audit_id,
                        "file_key": audit.excel_s3_key
                    },
                )
        if audit.json_s3_key:
            json_url = await generate_presigned_get_url(bucket_out, audit.json_s3_key, expires_in)
            logger.info(
                    "Generated JSON presigned URL",
                    extra={
                        "audit_id": audit_id,
                        "file_key": audit.json_s3_key
                    },
                )

        logger.info(
                "✅ Download links generated successfully",
                extra={
                    "audit_id": audit_id,
                    "excel_url": bool(excel_url),
                    "json_url": bool(json_url)    
                },
            )
    
        return {
            "audit_id": audit_id,
            "expires_in_seconds": expires_in,
            "excel_url": excel_url,
            "json_url": json_url,
        }

    except HTTPException:
        raise  # propagate FastAPI's intended error
    except Exception as e:
        logger.exception(
            "❌ Unexpected error while generating download links",
            extra={"audit_id": audit_id, "error": str(e)},
        )
        raise HTTPException(status_code=500, detail="Internal server error while generating links.")