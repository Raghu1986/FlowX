from sqlmodel import SQLModel, Field, JSON, Column
from datetime import datetime, UTC , timezone
from typing import Optional
from uuid import uuid4, UUID

class AuditStatus:
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

class ValidationRules(SQLModel, table=True):
    id: UUID = Field(primary_key=True, default_factory=uuid4)
    name: Optional[str] = None
    rules_json: dict = Field(sa_column=Column(JSON))
    created_on: datetime = Field(default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

class AuditLog(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    file_name: str
    rules_id: Optional[UUID] = None
    total_records: Optional[int] = None
    processed_records: Optional[int] = 0
    success_count: Optional[int] = None
    failure_count: Optional[int] = None
    progress_percent: Optional[float] = 0.0
    profiler_data: Optional[dict] = Field(sa_column=Column(JSON))
    status: Optional[str] = Field(default=AuditStatus.PENDING)
    error_message: Optional[str] = None
    excel_s3_key: Optional[str] = None
    json_s3_key: Optional[str] = None
    created_on: Optional[datetime] = Field(default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    updated_on: Optional[datetime] = Field(default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
