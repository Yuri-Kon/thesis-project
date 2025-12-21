from __future__ import annotations
from typing import Dict, Any
from uuid import uuid4
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from src.models.contracts import ProteinDesignTask
from src.models.db import TaskRecord
from src.workflow.workflow import run_task_sync

app = FastAPI(title="Protein Design Agent System (Mini Demo)")

# 简单的内存存储，之后可以换成数据库或文件
TASK_STORE: Dict[str, TaskRecord] = {}

class TaskCreateRequest(BaseModel):
    goal: str = Field(..., description="蛋白质设计任务目标(自然语言)")
    constraints: Dict[str, Any] = Field(
        default_factory=dict,
        description="结构化约束"
    )
    metadata: Dict[str, Any] = Field(default_factory=dict)

@app.post("/tasks", response_model=TaskRecord)
async def create_task(req: TaskCreateRequest):
    """创建一个任务并同步执行"""

    task_id = f"task_{uuid4().hex[:8]}"
    task = ProteinDesignTask(
        task_id=task_id,
        goal=req.goal,
        constraints=req.constraints,
        metadata=req.metadata,
    )

    record = run_task_sync(task)
    TASK_STORE[task_id] = record
    return record

@app.get("/tasks/{task_id}", response_model=TaskRecord)
async def get_task(task_id: str):
    """查看任务当前状态和摘要"""
    record = TASK_STORE.get(task_id)
    if record is None:
        raise HTTPException(status_code=404, detail="task not found")
    return record
