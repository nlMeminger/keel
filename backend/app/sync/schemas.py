import uuid
from datetime import datetime

from pydantic import BaseModel

from app.jobs.models import Job


class SyncTriggerRequest(BaseModel):
    # Omitted => every bank the caller has linked; set => just that one (API_SPEC.md §16).
    bank_id: uuid.UUID | None = None


class SyncTriggerResponse(BaseModel):
    job_id: uuid.UUID


class JobProgress(BaseModel):
    current: int
    total: int


class JobStatus(BaseModel):
    id: uuid.UUID
    type: str
    status: str
    progress: JobProgress | None
    started_at: datetime | None
    finished_at: datetime | None
    error: str | None

    @classmethod
    def from_job(cls, job: Job) -> "JobStatus":
        progress = None
        if job.progress_current is not None and job.progress_total is not None:
            progress = JobProgress(current=job.progress_current, total=job.progress_total)
        return cls(
            id=job.id,
            type=job.type,
            status=job.status,
            progress=progress,
            started_at=job.started_at,
            finished_at=job.finished_at,
            error=job.error,
        )
