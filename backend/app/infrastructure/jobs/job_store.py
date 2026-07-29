"""
Simple in-memory job store for tracking async QAOA optimization runs,
satisfying Phase 1's api-design.md pattern (POST /run returns 202 + job_id,
poll for status/result).

DELIBERATE SCOPE LIMITATION: this is a plain in-process dict, not Celery/
Redis or any persistent queue. It does not survive a server restart, and
does not work across multiple worker processes/replicas. That's a real
production gap — acceptable for this project's current single-process
deployment, but a genuine thing to fix (with Celery + Redis, both already
in Phase 1's planned tech stack) before this could run behind more than
one uvicorn worker.
"""
import uuid
from dataclasses import dataclass
from typing import Any


@dataclass
class Job:
    job_id: str
    status: str = "running"  # "running" | "completed" | "failed"
    result: Any = None
    error: str | None = None


class InMemoryJobStore:
    def __init__(self):
        self._jobs: dict[str, Job] = {}

    def create(self) -> str:
        job_id = str(uuid.uuid4())
        self._jobs[job_id] = Job(job_id=job_id)
        return job_id

    def mark_completed(self, job_id: str, result: Any) -> None:
        if job_id in self._jobs:
            self._jobs[job_id].status = "completed"
            self._jobs[job_id].result = result

    def mark_failed(self, job_id: str, error: str) -> None:
        if job_id in self._jobs:
            self._jobs[job_id].status = "failed"
            self._jobs[job_id].error = error

    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)


# Module-level singleton — simple, adequate for a single-process deployment.
# See module docstring for the real limitation this implies.
job_store = InMemoryJobStore()