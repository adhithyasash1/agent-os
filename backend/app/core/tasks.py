import json
import os
from datetime import datetime
from typing import List, Dict, Any

TASKS_FILE = "./data/tasks.jsonl"

def log_trajectory(
    task_id: str, 
    trajectory: List[Dict[str, Any]], 
    score: float, 
    context_used: Dict[str, str] = None,
    final_answer: str = "",
    critique: str = ""
):
    run_data = {
        "run_id": datetime.now().strftime("%Y%m%d%H%M%S"),
        "task_id": task_id,
        "trajectory": trajectory,
        "score": score,
        "context_used": context_used or {},
        "final_answer": final_answer,
        "critique": critique,
        "human_feedback": None,
        "timestamp": datetime.now().isoformat()
    }
    
    os.makedirs(os.path.dirname(TASKS_FILE), exist_ok=True)
    with open(TASKS_FILE, "a") as f:
        f.write(json.dumps(run_data) + "\n")

def get_runs():
    if not os.path.exists(TASKS_FILE):
        return []
    runs = []
    with open(TASKS_FILE, "r") as f:
        for line in f:
            runs.append(json.loads(line))
    return runs

def update_trajectory_feedback(task_id: str, feedback: Dict[str, Any]):
    if not os.path.exists(TASKS_FILE):
        return False
        
    runs = []
    updated = False
    with open(TASKS_FILE, "r") as f:
        for line in f:
            try:
                run = json.loads(line)
                if run.get("task_id") == task_id:
                    run["human_feedback"] = feedback
                    updated = True
                runs.append(run)
            except json.JSONDecodeError:
                continue
                
    if updated:
        # Write back atomically or overwrite
        with open(TASKS_FILE, "w") as f:
            for run in runs:
                f.write(json.dumps(run) + "\n")
    
    return updated
