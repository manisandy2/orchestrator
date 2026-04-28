import asyncio
import logging

from typing import Optional

from app.agents.reply_agent import reply_agent
from app.tools.crm_tool import complaint_agent
from app.agents.compliance_agent import compliance_agent
from app.agents.decision_agent import decision_agent
from app.utility.helper import build_complaint_link
from app.core.state import ReviewState
from app.utility.validators import validate_tone, validate_completeness
from app.filters.sensitive import _is_sensitive
from app.responses.blocked import _blocked_response

from app.services.reply.generator import _generate_reply
from app.services.reply.validator import _validate_reply
from app.services.reply.evaluate import _evaluate_reply
from app.responses.error import _error_response
logger = logging.getLogger(__name__)


# =========================
# Main Orchestrator
# =========================
async def process_review_task(data: dict) -> dict:
    state = ReviewState(data)
    job_id = state.job_id
    state.log("Processing started")

    try:
        logger.info(f"[{job_id}] Processing started")
        # =========================
        # STEP 0: Sensitive check
        # =========================
        if _is_sensitive(state.review):
            state.block_reply("Sensitive content")
            
            from app.services.db_service import save_review_state
            await save_review_state(state)
            
            return _blocked_response(job_id=job_id,
                review=state.review,
                rating=state.rating,
                location_name=state.location_name
                )

        # =========================
        # STEP 1: Decision agent
        # =========================
        # try:
        decision = await decision_agent(
            review=state.review,
            rating=state.rating,
            reviewer=state.reviewer,
            store=state.location_name,
        )
        
        state.issue_type = decision.get("classification", {}).get("issue_type", "other")
        state.issues = decision.get("issues", [])
        state.set_tone()


        # =========================
        # STEP 2: Complaint Ticket
        # =========================
        state.complaint_link = None
        if decision.get("create_ticket"):
            state.complaint_link = await _safe_create_complaint(state)
   

        # =========================
        # STEP 3: Reply Generation
        # =========================
        state.draft_response = await _generate_reply(state) or "Thank you for your feedback."

        # =========================
        # STEP 4: Clean and Validate Draft Quality
        # =========================
        max_quality_retries = 2
        for attempt in range(max_quality_retries):
            state.draft_response = _clean_reply(state.draft_response)
            
            tone_ok = validate_tone(state.draft_response, state.tone)
            complete_ok = validate_completeness(state.draft_response, state.issues)
            
            if tone_ok and complete_ok:
                break
                
            logger.info(f"[{job_id}] Quality mismatch (tone: {tone_ok}, complete: {complete_ok}) — regenerating (attempt {attempt + 1})")
            state.draft_response = await _generate_reply(state)
            
        state.draft_response = _clean_reply(state.draft_response)

        # =========================
        # STEP 5: Compliance agent
        # =========================

        validation = await _validate_reply(state)

        state.final_response = validation.get("reply")
        validation_status = validation.get("status")

        if validation_status == "blocked":
            state.needs_manual = True


        # =========================
        # STEP 6: Evaluation
        # =========================
        evaluation = await _evaluate_reply(
            review=state.review,
            rating=state.rating,
            reply=state.final_response
        )

        state.set_evaluation(evaluation)
        # =========================
        # STEP 7: Auto Improve
        # =========================
        if validation_status != "blocked" and evaluation.get("overall_score", 0) < 3:
            logger.info(f"[{job_id}] Low score → retry")

            improved = await _generate_reply(state)
            state.draft_response = _clean_reply(improved)

            validation = await _validate_reply(state)
            state.final_response = validation.get("reply")
            validation_status = validation.get("status")
            validation_reason = validation.get("reason")
            validation_flags = validation.get("flags", [])

            evaluation = await _evaluate_reply(
                review=state.review,
                rating=state.rating,
                reply=state.final_response
            )

            state.set_evaluation(evaluation)
        # =========================
        # FINAL RESPONSE
        # =========================
        logger.info(
            f"[{job_id}] Completed",
            extra={
                "rating": state.rating,
                "issue_type": state.issue_type,
                "score": state.overall_score,
                "needs_manual": state.needs_manual
            }
        )
        # =========================
        # SAVE + RESPONSE
        # =========================
        
        from app.services.db_service import save_review_state
        await save_review_state(state)

        logger.info(f"[{job_id}] Completed")
        return {
            "job_id": job_id,
            "status": "completed",

            "input": {
                "review": state.review,
                "rating": state.rating,
                "location_name": state.location_name,
            },

            "agent_1": {
                "sentiment": decision.get("classification", {}).get("sentiment"),
                "issue_type": state.issue_type,
                "issues": state.issues,
                "rating": state.rating,
                "confidence_score": decision.get("confidence", 0.0),
                "create_ticket": decision.get("create_ticket", False),
                "draft_reply": state.draft_response
            },

            "agent_2": {
                "status": validation.get("status"),
                "draft_reply": state.draft_response,
                "final_reply": state.final_response,
                "compliance_flags": validation.get("flags", []),
                "blocked_reason": validation.get("reason") if validation.get("status") == "blocked" else None,
                "modified": state.draft_response != state.final_response
            },

            "quality": {
                "tone": {
                    "score": state.tone_score,
                    "is_correct": (
                        (state.rating <= 2 and state.tone_score >= 3) or
                        (state.rating == 3 and state.tone_score >= 3) or
                        (state.rating >= 4 and state.tone_score >= 3)
                    ),
                    "expected": state.tone
                },
                "brand_voice": {
                    "score": state.brand_voice_score,
                    "is_consistent": state.brand_voice_score >= 3
                },
                "completeness": {
                    "score": state.completeness_score,
                    "is_complete": state.completeness_score >= 3
                },
                "overall": {
                    "score": state.overall_score,
                    "is_good": state.overall_score >= 3
                }
            },

            # Raw evaluation (keep for debugging)
            "evaluation": state.evaluation,

            "meta": {
                "needs_manual": state.needs_manual,
                "complaint_link": state.complaint_link,
            }
        }

    except Exception as e:
        logger.exception(f"[{job_id}] Processing failed")
        state.set_error(str(e))
        
        from app.services.db_service import save_review_state
        await save_review_state(state)
        
        return _error_response(job_id=job_id, message="Processing failed", details=str(e))


# =========================
# Reply deduplication
# =========================
def _clean_reply(text: str) -> str:
    if not text:
        return ""

    sentences = text.split(". ")
    seen = set()
    result = []

    for s in sentences:
        s = s.strip()
        if s and s not in seen:
            seen.add(s)
            result.append(s)

    return ". ".join(result)


# =========================
# Complaint creation (with retry)
# =========================
async def _safe_create_complaint(state: ReviewState) -> Optional[str]:
    state.log("Complaint creation started")

    max_retries = 2
    total_attempts = max_retries + 1

    # Basic validation  
    if not state.data:
        state.log("Complaint skipped: no data")
        return None

    for attempt in range(1, total_attempts + 1):
        try:
            state.increment_retry("complaint")
            state.log(f"Complaint attempt {attempt}/{total_attempts}")

            ticket = await complaint_agent(state.data)

            if ticket.get("status") == "created":
                ticket_id = ticket.get("ticket_id")
                if ticket_id:
                    link = build_complaint_link(ticket_id)
                    state.log(f"Complaint created: {ticket_id}")
                    state.add_history("complaint", "created", {"ticket_id": ticket_id, "link": link})
                    state.set_metric("complaint", "success", True)
                    return link

            state.log("Complaint API responded but ticket not created")

        except Exception as e:
            state.log(f"Complaint attempt {attempt + 1} failed: {e}")
            if attempt == max_retries - 1:
                state.set_metric("complaint", "error", str(e))
        
        if attempt < total_attempts:
            await asyncio.sleep(0.5)

    state.log("Complaint creation failed after retries")
    state.add_history("complaint", "failed")
    state.set_metric("complaint", "success", False)
    return None