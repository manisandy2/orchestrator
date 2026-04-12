import asyncio
import logging
import uuid

from fastapi import APIRouter, HTTPException
from app.services.orchestrator import process_review_task
from app.schemas.review_schema import ReviewRequest

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/process-review")
async def process_review(payload: ReviewRequest):
    
    
    job_id = str(uuid.uuid4())
    logger.info(f"[{job_id}] Request received for location: {payload.location_name}")

    data = {
        "job_id": job_id,
        "review": payload.comment,
        "rating": payload.star_rating,
        "reviewer": payload.reviewer,
        "review_date": payload.review_date,
        "location_name": payload.location_name,
    }

    try:
        logger.info(f"[{job_id}] Process start")
        # Run the task synchronously with a 30-second timeout
        result = await asyncio.wait_for(process_review_task(data), timeout=130.0)
        
        logger.info(f"[{job_id}] Process completed successfully")
        return {
            "job_id": job_id,
            "status": "success",
            "data": result
        }

    except asyncio.TimeoutError:
        logger.error(f"[{job_id}] Processing timeout after 30 seconds")
        raise HTTPException(
            status_code=504,
            detail={
                "status": "failed",
                "message": "Processing timeout",
            },
        )

    except Exception as e:
        # Don't return str(e) to the client on 500 errors to prevent info leakage.
        # Log the full exception internally instead.
        logger.exception(f"[{job_id}] Processing failed: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "status": "failed",
                "message": "Internal server error",
            },
        )