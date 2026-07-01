from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_run_job_service, get_run_service
from app.schemas.runs import RunCreateRequest, RunIndex, RunJob, RunSummary
from app.services.run_job_service import RunJobService
from app.services.run_service import RunService


router = APIRouter(prefix="/api/runs", tags=["runs"])


@router.get("", response_model=list[RunSummary])
def list_runs(run_service: RunService = Depends(get_run_service)) -> list[RunSummary]:
    return run_service.list_runs()


@router.get("/{run_id}", response_model=RunIndex)
def get_run(run_id: str, run_service: RunService = Depends(get_run_service)) -> RunIndex:
    run = run_service.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found.")
    return run


@router.delete("/{run_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_run(run_id: str, run_service: RunService = Depends(get_run_service)) -> None:
    try:
        run_service.delete_run(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found.") from exc


@router.post("", response_model=RunIndex, status_code=status.HTTP_201_CREATED)
def create_run(
    request: RunCreateRequest,
    run_service: RunService = Depends(get_run_service),
) -> RunIndex:
    try:
        return run_service.create_run(request)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/jobs", response_model=RunJob, status_code=status.HTTP_202_ACCEPTED)
def start_run_job(
    request: RunCreateRequest,
    run_job_service: RunJobService = Depends(get_run_job_service),
) -> RunJob:
    try:
        return run_job_service.start_job(request)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/jobs/{job_id}", response_model=RunJob)
def get_run_job(
    job_id: str,
    run_job_service: RunJobService = Depends(get_run_job_service),
) -> RunJob:
    job = run_job_service.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run job not found.")
    return job
