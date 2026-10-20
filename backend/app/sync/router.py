import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as DbSession

from app.auth.models import User
from app.core.envelope import Envelope
from app.core.errors import AppError
from app.database import get_db
from app.dependencies import get_current_user
from app.jobs.models import Job
from app.sync.schemas import JobStatus

router = APIRouter(prefix="/sync", tags=["sync"])


@router.get("/jobs/{job_id}", response_model=Envelope[JobStatus])
def get_job(
    job_id: uuid.UUID, db: DbSession = Depends(get_db), user: User = Depends(get_current_user)
) -> dict[str, JobStatus]:
    job = db.get(Job, job_id)
    if job is None or job.owner_id != user.id:
        raise AppError(404, "not_found", "Job not found.")
    return {"data": JobStatus.from_job(job)}
