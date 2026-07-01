from __future__ import annotations

import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from app.core.config import settings
from app.schemas.runs import ProgressUpdate, RunCreateRequest, RunJob
from app.services.run_service import RunService


def utc_now_job_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class RunJobService:
    def __init__(self, run_service: RunService) -> None:
        self._run_service = run_service
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="run-job")
        self._lock = threading.Lock()
        self._jobs: dict[str, RunJob] = {}

    def start_job(self, request: RunCreateRequest) -> RunJob:
        job_id = uuid.uuid4().hex
        job = RunJob(
            job_id=job_id,
            status="queued",
            created_at=utc_now_job_iso(),
            last_updated_at=utc_now_job_iso(),
            stall_timeout_s=settings.run_job_stall_timeout_seconds,
            execution_mode=request.execution_mode,
            prompt_set_id=request.prompt_set_id,
            input_image=request.input_image,
            model_ids=request.model_ids,
            prompt_keys=request.prompt_keys,
            message="Queued.",
        )
        with self._lock:
            self._jobs[job_id] = job
        self._executor.submit(self._run_job, job_id, request)
        return job

    def get_job(self, job_id: str) -> RunJob | None:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return None
            job_copy = job.model_copy(deep=True)
        return self._with_derived_status(job_copy)

    def _run_job(self, job_id: str, request: RunCreateRequest) -> None:
        self._update_job(
            job_id,
            status="running",
            started_at=utc_now_job_iso(),
            message="Starting run.",
        )
        try:
            run = self._run_service.create_run(request, progress_callback=lambda update: self._apply_progress(job_id, update))
            self._update_job(
                job_id,
                status="completed",
                finished_at=utc_now_job_iso(),
                completed_steps=self.get_job(job_id).total_steps if self.get_job(job_id) else 0,
                run_id=run.run_id,
                message=f"Completed run {run.run_id}.",
            )
        except Exception as exc:
            self._update_job(
                job_id,
                status="failed",
                finished_at=utc_now_job_iso(),
                error=str(exc),
                message="Run failed.",
            )

    def _apply_progress(self, job_id: str, update: ProgressUpdate) -> None:
        self._update_job(
            job_id,
            completed_steps=update.completed_steps,
            total_steps=update.total_steps,
            current_model_id=update.current_model_id,
            current_prompt_key=update.current_prompt_key,
            message=update.message,
        )

    def _update_job(self, job_id: str, **changes: object) -> None:
        with self._lock:
            job = self._jobs[job_id]
            update_timestamp = utc_now_job_iso()
            next_model_id = changes.get("current_model_id", job.current_model_id)
            next_prompt_key = changes.get("current_prompt_key", job.current_prompt_key)
            if (
                next_model_id != job.current_model_id
                or next_prompt_key != job.current_prompt_key
            ):
                job.step_started_at = update_timestamp
            for key, value in changes.items():
                setattr(job, key, value)
            job.last_updated_at = update_timestamp

    def _with_derived_status(self, job: RunJob) -> RunJob:
        if job.status != "running":
            return job
        if not job.last_updated_at or not job.stall_timeout_s:
            return job

        last_updated = datetime.fromisoformat(job.last_updated_at.replace("Z", "+00:00"))
        seconds_since_update = (datetime.now(timezone.utc) - last_updated).total_seconds()
        if seconds_since_update < job.stall_timeout_s:
            return job

        job.status = "stalled"
        stalled_for = int(seconds_since_update)
        step_started = job.step_started_at or job.last_updated_at
        job.message = (
            f"No progress update for {stalled_for}s while waiting on "
            f"{job.current_model_id or 'current model'} / {job.current_prompt_key or 'current prompt'} "
            f"(step started at {step_started})."
        )
        return job
