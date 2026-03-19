from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class PredictRequest(BaseModel):
    task_id: str
    step_id: str
    inputs: Dict[str, Any] = Field(default_factory=dict)


class JobAccepted(BaseModel):
    job_id: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    failure: Optional[Dict[str, Any]] = None


class ArtifactItem(BaseModel):
    name: str
    url: str
    type: str = "file"


class ResultsResponse(BaseModel):
    job_id: str
    outputs: Dict[str, Any] = Field(default_factory=dict)
    artifacts: List[ArtifactItem] = Field(default_factory=list)
