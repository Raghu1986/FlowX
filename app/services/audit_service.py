from datetime import datetime, UTC , timezone
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select
from app.models import AuditLog
from uuid import UUID

async def create_audit_entry(session: AsyncSession, file_name: str, rules_id: UUID ) -> str:
    audit = AuditLog(file_name=file_name,rules_id=rules_id)
    session.add(audit)
    await session.commit()
    await session.refresh(audit)
    return audit.id

async def update_audit_status(session: AsyncSession, audit_id: str, status: str, **fields):
    result = await session.exec(select(AuditLog).where(AuditLog.id == audit_id))
    audit = result.first()
    if not audit:
        return
    for k, v in fields.items():
        setattr(audit, k, v)
    audit.status = status
    audit.updated_on = datetime.now(timezone.utc).replace(tzinfo=None)
    session.add(audit)
    await session.commit()

async def update_progress(session: AsyncSession, audit_id: str, processed: int, total: int):
    result = await session.exec(select(AuditLog).where(AuditLog.id == audit_id))
    audit = result.first()
    if not audit:
        return
    audit.processed_records = processed
    audit.total_records = total
    audit.progress_percent = round((processed / total) * 100, 2) if total else 0
    audit.updated_on = datetime.now(timezone.utc).replace(tzinfo=None)
    session.add(audit)
    await session.commit()

async def get_audit_by_id(session: AsyncSession, audit_id: str):
    result = await session.exec(select(AuditLog).where(AuditLog.id == audit_id))
    return result.first()
