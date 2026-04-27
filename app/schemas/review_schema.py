from pydantic import BaseModel,Field
from typing import Optional


class ReviewRequest(BaseModel):
    comment: str = Field(
        ..., 
        min_length=1, 
        description="The actual text of the customer review.",
        example="The service was excellent, and the staff was very helpful!"
    )
    star_rating: int = Field(
        ..., 
        ge=1, 
        le=5, 
        description="Rating given by the customer (1 to 5 stars).",
        example=5
    )
    reviewer: Optional[str] = Field(
        default="Customer",
        description="Name of the person who wrote the review.",
        example="John Doe"
    )
    location_name: str = Field(
        ..., 
        min_length=1, 
        description="The branch or store name where the review was left.",
        example="Poorvika Mobiles Chennai"
    )
    review_date: Optional[str] = Field(
        default=None,
        description="Date when the review was posted (ISO format preferred).",
        example="2024-03-27T10:00:00Z"
    )