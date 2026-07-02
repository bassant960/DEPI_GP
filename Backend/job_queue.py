import uuid
import asyncio
import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel


# ============================================================
# Job Status Enum
# ============================================================

class JobStatus(str, Enum):
    QUEUED     = "queued"
    PROCESSING = "processing"
    DONE       = "done"
    FAILED     = "failed"


# ============================================================
# Job Model
# ============================================================

class Job(BaseModel):
    id:          str
    user_email:  str
    outfit_url:  str
    cloth_type:  str             = "upper"
    status:      JobStatus       = JobStatus.QUEUED
    result_url:  Optional[str]   = None
    error:       Optional[str]   = None
    created_at:  datetime.datetime = None
    updated_at:  datetime.datetime = None

    class Config:
        use_enum_values = True


# ============================================================
# Processing Queue
# ============================================================

class ProcessingQueue:
    """
    In-memory job queue for virtual try-on requests.
    Each job moves through: QUEUED → PROCESSING → DONE / FAILED
    """

    def __init__(self):
        self._jobs: dict[str, Job] = {}   # job_id → Job
        self._lock = asyncio.Lock()

    # ── Add a new job ──────────────────────────────────────

    async def add_job(self, user_email: str, outfit_url: str, cloth_type: str = "upper") -> Job:
        """Creates a new job and adds it to the queue."""
        async with self._lock:
            job = Job(
                id          = uuid.uuid4().hex,
                user_email  = user_email,
                outfit_url  = outfit_url,
                cloth_type  = cloth_type,
                status      = JobStatus.QUEUED,
                created_at  = datetime.datetime.utcnow(),
                updated_at  = datetime.datetime.utcnow(),
            )
            self._jobs[job.id] = job
            return job

    # ── Get a single job ───────────────────────────────────

    def get_job(self, job_id: str) -> Optional[Job]:
        """Returns a job by ID, or None if not found."""
        return self._jobs.get(job_id)

    # ── Get all jobs for a user ────────────────────────────

    def get_user_jobs(self, user_email: str) -> list[Job]:
        """Returns all jobs belonging to a specific user, newest first."""
        return sorted(
            [j for j in self._jobs.values() if j.user_email == user_email],
            key=lambda j: j.created_at,
            reverse=True
        )

    # ── Queue stats ────────────────────────────────────────

    def stats(self) -> dict:
        """Returns a summary count of jobs by status."""
        jobs = list(self._jobs.values())
        return {
            "total":      len(jobs),
            "queued":     sum(1 for j in jobs if j.status == JobStatus.QUEUED),
            "processing": sum(1 for j in jobs if j.status == JobStatus.PROCESSING),
            "done":       sum(1 for j in jobs if j.status == JobStatus.DONE),
            "failed":     sum(1 for j in jobs if j.status == JobStatus.FAILED),
        }

    # ── Internal status updates ────────────────────────────

    async def _mark_processing(self, job_id: str):
        async with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job.status     = JobStatus.PROCESSING
                job.updated_at = datetime.datetime.utcnow()

    async def _mark_done(self, job_id: str, result_url: str):
        async with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job.status     = JobStatus.DONE
                job.result_url = result_url
                job.updated_at = datetime.datetime.utcnow()

    async def _mark_failed(self, job_id: str, error: str):
        async with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job.status     = JobStatus.FAILED
                job.error      = error
                job.updated_at = datetime.datetime.utcnow()

    # ── Run a job through the model ────────────────────────

    async def process_job(self, job_id: str, person_image_path: str, model) -> Job:
        """
        Runs a queued job through the AI model.

        Args:
            job_id       : ID of the job to process
            person_image : UploadFile from the FastAPI request
            model        : ModelWrapper instance from model.py

        Returns:
            The updated Job object
        """
        job = self._jobs.get(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")

        await self._mark_processing(job_id)

        try:
            result = await model.run(
                person_image_path=person_image_path, 
                outfit_url=job.outfit_url,
                cloth_type=job.cloth_type
            )
            await self._mark_done(job_id, result["result_url"])

        except Exception as e:
            await self._mark_failed(job_id, str(e))

        return self._jobs[job_id]


# ============================================================
# Singleton instance — import this in main.py
# ============================================================

job_queue = ProcessingQueue()