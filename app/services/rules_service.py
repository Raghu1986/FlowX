# app/services/rules_service.py
from typing import Optional, Dict
from uuid import UUID
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select
from app.models import ValidationRules

async def get_rules_json(session: AsyncSession, rules_id: UUID) -> Optional[Dict]:
    result = await session.exec(select(ValidationRules).where(ValidationRules.id == rules_id))
    rules = result.first()
    return rules.rules_json if rules else None
