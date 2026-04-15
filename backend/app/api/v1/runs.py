from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.core.tasks import get_runs, update_trajectory_feedback

router = APIRouter()


@router.get("/")
async def list_runs():
    try:
        return get_runs()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read runs: {e}")


@router.get("/{run_id}")
async def get_run(run_id: str):
    runs = get_runs()
    for run in runs:
        if run["run_id"] == run_id:
            return run
    raise HTTPException(status_code=404, detail="Run not found")

class FeedbackRequest(BaseModel):
    score: int
    comment: str = ""

@router.post("/{task_id}/feedback")
async def add_feedback(task_id: str, feedback: FeedbackRequest):
    payload = {"score": feedback.score, "comment": feedback.comment}
    updated = update_trajectory_feedback(task_id, payload)
    if not updated:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"status": "success"}
