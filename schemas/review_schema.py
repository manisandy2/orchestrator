from pydantic import BaseModel,Field
from typing import Optional


class  ReviewRequest(BaseModel):
    comment: str = Field(..., min_length=1)
    star_rating: int = Field(..., ge=1, le=5)
    reviewer: Optional[str] = "Customer"
    location_name: str = Field(..., min_length=1)
    review_date: Optional[str] = None