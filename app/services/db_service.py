import json
from typing import Any
import logging
from app.core.database import db
from app.core.state import ReviewState

logger = logging.getLogger(__name__)

async def save_review_state(state: ReviewState) -> None:
    """Save the ReviewState into the PlanetScale database asynchronously."""
    table = "review_orchestration_state"
    columns = [
        "job_id", "review_text", "rating", "reviewer", "location_name", "review_date",
        "sentiment", "issue_type", "key_issues", "tone",
        "draft_response", "final_response", "response_type",
        "compliance_status", "compliance_reason", "needs_manual", "block_public_reply",
        "tone_score", "brand_voice_score", "completeness_score", "overall_score",
        "error", "logs", "history"
    ]
    
    def safe_json(val: Any) -> str:
        return json.dumps(val) if val is not None else None

    row = (
        state.job_id,
        state.review,
        state.rating,
        state.reviewer,
        state.location_name,
        state.review_date,
        state.sentiment,
        state.issue_type,
        safe_json(state.issues),
        state.tone,
        state.draft_response,
        state.final_response,
        state.response_type,
        state.compliance_status,
        state.compliance_reason,
        bool(state.needs_manual),
        bool(state.block_public_reply),
        state.tone_score,
        state.brand_voice_score,
        state.completeness_score,
        state.overall_score,
        state.error,
        safe_json(state.logs),
        safe_json(state.history)
    )

    try:
        # Pymysql is synchronous, so we just call it.
        # In a very high throughput async system, this could be wrapped in asyncio.to_thread
        db.execute_batch_upsert(
            table=table,
            columns=columns,
            rows=[row],
            unique_key="job_id"
        )
        logger.info(f"[{state.job_id}] Saved ReviewState to database.")
    except Exception as e:
        logger.error(f"[{state.job_id}] Failed to save ReviewState to database: {e}")
