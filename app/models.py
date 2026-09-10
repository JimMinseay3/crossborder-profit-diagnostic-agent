from typing import Any, Literal

from pydantic import BaseModel, Field


class RunRequest(BaseModel):
    example: str | None = None
    file_name: str | None = None
    file_content: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)


class Step(BaseModel):
    name: str
    status: Literal["completed", "warning"] = "completed"
    detail: str


class RunRecord(BaseModel):
    run_id: str
    status: Literal["completed", "failed"]
    created_at: str
    input_summary: str
    steps: list[Step]
    evidence: list[dict[str, Any]]
    result: dict[str, Any]
    warnings: list[str]
    confidence: float = Field(ge=0, le=1)
    needs_human_review: bool
    review_reasons: list[str]
    model_provider: str
    run_mode: str

