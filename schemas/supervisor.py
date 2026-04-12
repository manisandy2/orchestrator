from pydantic import BaseModel, Field
from typing import Literal


class Classification(BaseModel):
    sentiment: Literal["positive", "neutral", "negative"]
    issue_type: Literal["service", "staff", "product", "pricing", "hygiene", "delay", "other"]
    rating: int = Field(..., ge=1, le=5)


class SupervisorResponse(BaseModel):
    classification: Classification
    issues: list[str]
    severity: Literal["low", "medium", "high"]
    action: Literal["reply", "complaint"]
    create_ticket: bool
    response: str
    reason: str
    confidence: float = Field(default=0.9, ge=0.0, le=1.0)
