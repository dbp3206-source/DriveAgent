import asyncio
from time import time

from fastapi import APIRouter, HTTPException, Response

from app.api.dependencies import CurrentUser
from app.core.config import get_settings
from app.services.relational_evaluation import evaluation_queue

router = APIRouter(prefix="/api/evaluation-jobs", tags=["evaluation"])


@router.post("", status_code=202)
async def enqueue_evaluation(user: CurrentUser, response: Response):
    response.headers["Cache-Control"] = "no-store"
    try:
        job_id = await asyncio.to_thread(
            lambda: evaluation_queue(get_settings()).enqueue(user.id, time())
        )
    except ValueError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    return {"job_id": job_id, "scope": "offline_regression", "status": "queued"}


@router.get("/{job_id}")
async def read_evaluation(job_id: str, user: CurrentUser, response: Response):
    response.headers["Cache-Control"] = "no-store"
    job = await asyncio.to_thread(lambda: evaluation_queue(get_settings()).get(user.id, job_id))
    if job is None:
        raise HTTPException(status_code=404, detail="Evaluation job not found")
    return job


@router.get("")
async def recent_evaluations(user: CurrentUser, response: Response):
    response.headers["Cache-Control"] = "no-store"
    return {
        "items": await asyncio.to_thread(lambda: evaluation_queue(get_settings()).recent(user.id))
    }
