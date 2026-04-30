import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.core.database import db
from app.schemas.review_schema import ReviewRequest
from app.services.orchestrator import process_review_task

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/process-review",tags=["reviews-read-from-web"])
async def process_review(payload: ReviewRequest):
    
    job_id = str(uuid.uuid4())
    
    logger.info(
        f"[{job_id}] Request received for location: {payload.location_name}")

    data = {
        "job_id": job_id,
        "review": payload.comment,
        "rating": payload.star_rating,
        "reviewer": payload.reviewer,
        "review_date": payload.review_date,
        "location_name": payload.location_name,
        "created_at": datetime.now(timezone.utc).isoformat()
    }

    try:
        logger.info(f"[{job_id}] Process start")
        # Run the task synchronously with a 130-second timeout
        result = await asyncio.wait_for(process_review_task(data), timeout=130.0)
        
        if result and result.get("status") == "failed":
            logger.error(f"[{job_id}] Process failed internally")
            raise HTTPException(
                status_code=500,
                detail={
                    "status": "failed",
                    "message": "Processing failed internally",
                    "error": result.get("error")
                }
            )
        
        logger.info(f"[{job_id}] Process completed successfully")
        return {
            "job_id": job_id,
            "status": "success",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": result
        }

    except asyncio.TimeoutError:
        logger.error(f"[{job_id}] Processing timeout after 130 seconds")
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


@router.post("/process-from-db", tags=["reviews-read-db"])
async def process_reviews_from_db(
    location_filter: Optional[str] = Query( None, description="Filter reviews by exact branch/location name.", examples={
        "sample": {
            "summary": "Example location",
            "value": "Chennai"
        }
    }
),
    date_from: Optional[str] = Query(None, description="Start date for fetching reviews (YYYY-MM-DD). Defaults to 30 days ago."),
    date_to: Optional[str] = Query(None, description="End date for fetching reviews (YYYY-MM-DD). Defaults to today."),
    max_reviews: int = Query(50, ge=1, le=200, description="Maximum number of reviews to process in this batch.")
):
    job_id = str(uuid.uuid4())
    logger.info(f"[{job_id}] Batch processing started")

    # Default dates
    if not date_from:
        date_from = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    if not date_to:
        date_to = datetime.now().strftime("%Y-%m-%d")
    # location_reviews_test or location_reviews_test  table name
    # ✅ Query (only empty replies)
    query = """
        SELECT reviewId, name, comment, rating, createTime, reviewer_displayName
        FROM location_reviews
        WHERE (reviewReply IS NULL OR reviewReply = '')
       
    """

    params = []

    if location_filter:
        query += " AND name = %s"
        params.append(location_filter)

    query += " AND createTime >= %s AND createTime <= %s"
    params.append(f"{date_from} 00:00:00")
    params.append(f"{date_to} 23:59:59")

    query += f" LIMIT {max_reviews}"

    # ✅ Fetch from DB
    try:
        reviews = db.execute_query(query, tuple(params))
        logger.info(f"[{job_id}] Fetched {len(reviews)} reviews")
    except Exception as e:
        logger.exception(f"[{job_id}] DB query failed")
        raise HTTPException(status_code=500, detail="Query failed")

    if not reviews:
        return {"message": "No pending reviews"}

    # Define a semaphore to limit concurrency
    semaphore = asyncio.Semaphore(5)
    
    async def process_with_semaphore(row):
        review_id = row.get("reviewId")
        try:
            # Safely serialize datetime objects to ISO strings
            review_date = row.get("createTime")
            if isinstance(review_date, datetime):
                review_date = review_date.isoformat()
            elif review_date is not None:
                review_date = str(review_date)

            data = {
                "job_id": review_id,
                "review": row.get("comment"),
                "rating": row.get("rating"),
                "reviewer": row.get("reviewer_displayName"),
                "review_date": review_date,
                "location_name": row.get("name"),
            }
            logger.info(f"[{job_id}] Processing review: {review_id}")
            
            async with semaphore:
                result = await asyncio.wait_for(process_review_task(data), timeout=130.0)

            return {
                "reviewId": review_id,
                "status": "processed",
                "result": result
            }

        except asyncio.TimeoutError:
            logger.error(f"[{job_id}] Timeout for review {review_id}")
            return {
                "reviewId": review_id,
                "status": "failed",
                "error": "Processing timeout"
            }
        except Exception as e:
            logger.error(f"[{job_id}] Failed for review {review_id}: {e}")
            return {
                "reviewId": review_id,
                "status": "failed",
                "error": str(e)
            }

    # ✅ Process reviews concurrently
    tasks = [process_with_semaphore(row) for row in reviews]
    results = await asyncio.gather(*tasks)

    logger.info(f"[{job_id}] Batch processing completed")

    return {
        "job_id": job_id,
        "processed": len(results),
        "results": results
    }