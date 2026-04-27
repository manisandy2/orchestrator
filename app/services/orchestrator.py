import asyncio
import logging

from typing import Optional

from app.agents.reply_agent import reply_agent
from app.tools.crm_tool import complaint_agent
from app.agents.supervisor_agent import decision_agent, compliance_agent
from app.utility.helper import build_complaint_link
from app.core.state import ReviewState
from app.utility.validators import validate_tone, validate_completeness
from app.filters.sensitive import _is_sensitive
from app.responses.blocked import _blocked_response
from app.services.review_evaluator import evaluate_reply

logger = logging.getLogger(__name__)

SAFE_ESCALATION_REPLY = (
    "We take this matter seriously. Kindly share more details "
    "through the provided link so we can investigate further."
)


UNSAFE_PATTERNS = [
    "we admit",
    "our mistake",
    "we were wrong",
    "staff was wrong",
    "it was our fault",
    "we take full responsibility"
]



# =========================
# Main Orchestrator
# =========================
async def process_review_task(data: dict) -> dict:
    state = ReviewState(data)
    job_id = state.job_id
    state.log("Processing started")

    logger.info(f"[{job_id}] Processing started")

    try:
        # =========================
        # STEP 0: Sensitive check
        # =========================
        if _is_sensitive(state.review):
            logger.info(f"[{job_id}] Sensitive content detected — blocking")
            state.block_reply("Sensitive content")
            
            from app.services.db_service import save_review_state
            await save_review_state(state)
            
            return _blocked_response(job_id)

        # =========================
        # STEP 1: Decision agent
        # =========================
        decision = await decision_agent(
            review=state.review,
            rating=state.rating,
            reviewer=state.reviewer,
            store=state.location_name,
        )

        # state.add_history("decision", "completed", decision)
        # state.set_metric("decision", "success", True)
        state.issue_type = decision.get("classification", {}).get("issue_type", "other")
        state.issues = decision.get("issues", [])

        # Tone mapping (FIXED)
        state.set_tone()

        # Flag for manual review on low confidence or missing data
        # confidence = decision.get("confidence", 0.9)
        # if confidence < 0.6 or not state.review:
        #     state.needs_manual = True

        # =========================
        # STEP 2: Complaint Ticket
        # =========================
        if decision.get("create_ticket"):
            complaint_link = await _safe_create_complaint(state)
        else:
            complaint_link = None
            
        state.complaint_link = complaint_link

        # =========================
        # STEP 3: Reply Generation
        # =========================
        reply = await _generate_reply(state)
        state.draft_response = reply or "Thank you for your feedback."

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

        validation_reason = validation.get("reason")
        validation_flags = validation.get("flags", [])

        if validation_status == "blocked":
            state.needs_manual = True

        # state.set_metric("validation", "completed", True)

        logger.info(f"[{job_id}] Processing complete")

        # =========================
        # STEP 6: Evaluation
        # =========================
        evaluation = await evaluate_reply(
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

            evaluation = await evaluate_reply(
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

        # return {
        #     "job_id": job_id,
        #     "status": "completed",

        #     "input": {
        #         "review": state.review,
        #         "rating": state.rating,
        #         "location_name": state.location_name,
        #     },
        #     "agent_1": {
        #         "sentiment": decision.get("classification", {}).get("sentiment"),
        #         "issue_type": state.issue_type,
        #         "issues": state.issues,
        #         "rating": state.rating,
        #         "confidence_score": decision.get("confidence", 0.0),
        #         "create_ticket": decision.get("create_ticket", False),
        #         "draft_reply": state.draft_response
        #     },
        #     "agent_2": {
        #         "status": validation_status,  # or "blocked" (you should derive this)
        #         "draft_reply": state.draft_response,
        #         "final_reply": state.final_response,
        #         "compliance_flags": validation_flags,
        #         "blocked_reason": validation_reason if validation_status == "blocked" else None,
        #         "modified": state.draft_response != state.final_response
                
        #     },
        #     "evaluation": state.evaluation,
        #     "meta": {
        #         "needs_manual": state.needs_manual,
        #         "complaint_link": complaint_link,
        #     }
        # }
        
        from app.services.db_service import save_review_state
        await save_review_state(state)
        
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
                "status": validation_status,
                "draft_reply": state.draft_response,
                "final_reply": state.final_response,
                "compliance_flags": validation_flags,
                "blocked_reason": validation_reason if validation_status == "blocked" else None,
                "modified": state.draft_response != state.final_response
            },

            # ✅ NEW: QUALITY SUMMARY
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
                "complaint_link": complaint_link,
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


# =========================
# Reply generation (with retry)
# =========================
async def _generate_reply(state: ReviewState) -> str:
    state.log("Reply generation started")
    max_retries = 2

    for attempt in range(max_retries):
        try:
            state.increment_retry("reply")
            state.log(f"Reply attempt {attempt + 1}")

            reply = await reply_agent(
                review=state.review,
                rating=state.rating,
                reviewer=state.reviewer,
                store=state.location_name,
                issue_type=state.issue_type,
                tone=state.tone,
                issues=state.issues,
                complaint_link=state.complaint_link
            )

            if reply and isinstance(reply, str):
                reply = reply.strip()
                if not _is_bad_reply(reply, state.rating):
                    state.log("Reply generated successfully")
                    state.set_metric("reply", "success", True)
                    return reply
                state.log("Reply failed quality check, retrying")

        except Exception as e:
            state.log(f"Reply attempt {attempt + 1} failed: {e}")
            if attempt == max_retries - 1:
                state.set_metric("reply", "error", str(e))

    # Fallback
    state.log("Using fallback reply")
    fallback = (
        "We're sorry for your experience. Please share more details so we can assist you."
        if state.rating and state.rating <= 2
        else "Thank you for your feedback. We will look into this."
    )
    state.add_history("reply", "fallback", fallback)
    state.set_metric("reply", "fallback_used", True)
    return fallback


# =========================
# Compliance validation
# =========================
async def _validate_reply(state: ReviewState) -> dict:
    state.log("Validation started")
    
    SAFE_BLOCK_REPLY = SAFE_ESCALATION_REPLY

    try:
        result = await compliance_agent(
            review=state.review,
            rating=state.rating,
            draft_reply=state.draft_response,
            issue_type=state.issue_type,
            reviewer=state.reviewer,
            store=state.location_name,
        )

        if not result or not isinstance(result, dict):
            raise ValueError("Invalid compliance response format")

        status = result.get("status")
        final_reply = result.get("final_reply")
        reason = result.get("reason", "")

        valid_statuses = {"approved", "modified", "blocked"}
        if status not in valid_statuses:
            raise ValueError(f"Unexpected compliance status: {status!r}")
        
        # =========================
        # APPROVED
        # =========================

        if status == "approved":
            reply = final_reply or state.draft_response or "Thank you for your feedback."

            

            state.log("Reply approved")
            state.add_history("validation", "approved", 
                              {"reply": reply, "reason": reason})
            return {
                "status": "approved",
                "reply": reply,
                "reason": reason,
                "flags": []
            }

        if status == "modified":
            if not final_reply:
                state.log("Empty modified reply — manual review required")
                state.needs_manual = True
                state.block_public_reply = True
                state.add_history("validation", "manual_review", {
                    "original": state.draft_response,
                    "modified": final_reply,
                    "reason": "empty_modified_reply",
                })
                return {
                    "status": "blocked",
                    "reply": SAFE_BLOCK_REPLY,
                    "reason": "Compliance returned an empty modified reply; manual review required",
                    "flags": ["manual_review", "empty_modified_reply"]
                }

            # Safety check: do not publish the original draft when compliance
            # says it needed a large rewrite. Escalate for human review instead.
            if not _is_safe_modification(state.draft_response, final_reply):
                state.log("Compliance modification too large — manual review required")
                state.needs_manual = True
                state.block_public_reply = True
                state.add_history("validation", "manual_review", {
                    "original": state.draft_response,
                    "modified": final_reply,
                    "reason": "modification_too_large",
                })
                return {
                    "status": "blocked",
                    "reply": SAFE_BLOCK_REPLY,
                    "reason": "Compliance rewrite changed too much; manual review required",
                    "flags": ["manual_review", "modification_too_large"]
                }

            # Extra compliance guard: unsafe modified replies must not cause
            # the original draft to be approved.
            
            if any(word in final_reply.lower() for word in UNSAFE_PATTERNS):
                state.log("Unsafe wording detected in modified reply — manual review required")
                state.needs_manual = True
                state.block_public_reply = True
                state.add_history("validation", "manual_review", {
                    "original": state.draft_response,
                    "modified": final_reply,
                    "reason": "unsafe_modified_reply",
                })
                return {
                    "status": "blocked",
                    "reply": SAFE_BLOCK_REPLY,
                    "reason": "Unsafe wording detected in modified reply; manual review required",
                    "flags": ["manual_review", "unsafe_modified_reply"]
                }

            state.log("Reply modified by compliance")
            state.add_history("validation", "modified", {
                "original": state.draft_response,
                "modified": final_reply,
                "reason": reason,
            })
            return {
                "status": "modified",
                "reply": final_reply,
                "reason": reason,
                "flags": ["tone_adjusted"]
            }

        if status == "blocked":
            state.log("Reply blocked")
            state.needs_manual = True
            state.block_public_reply = True

            return {
                "status": "blocked",
                "reply": SAFE_BLOCK_REPLY,
                "reason": reason,
                "flags": ["sensitive"]
            }
                # fallback
        return {
            "status": "approved",
            "reply": state.draft_response,
            "reason": "Unknown status fallback",
            "flags": ["fallback"]
        }

    except Exception as e:
        logger.exception(f"Validation error: {e}")
        state.log(f"Validation failed: {e}")
        state.add_history("validation", "error", {"error": str(e)})
        state.needs_manual = True
        return {
            "status": "blocked",
            "reply": SAFE_BLOCK_REPLY,
            "reason": "Validation failed, manual review required",
            "flags": ["error", "manual_review"]
        }


# =========================
# Modification safety guard
# =========================
def _is_safe_modification(original: str, modified: str) -> bool:
    if not original or not modified:
        return False

    # Reject if length grew by more than 50% (was 30% — too aggressive for compliance edits)
    if len(modified) > len(original) * 1.5:
        return False

    # Reject if word overlap drops below 30% (was 50% — too aggressive)
    orig_words = set(original.lower().split())
    mod_words = set(modified.lower().split())
    common = orig_words & mod_words

    if orig_words and len(common) < len(orig_words) * 0.3:
        return False

    return True


# =========================
# Reply quality check
# =========================
def _is_bad_reply(reply: str, rating: int) -> bool:
    if not reply:
        return True

    words = reply.split()
    if len(words) < 10:
        return True

    if "." not in reply:
        return True

    if rating and rating <= 2:
        if not any(word in reply.lower() for word in ["sorry", "apolog", "regret"]):
            return True

    sentences = [s.strip() for s in reply.split(".") if s.strip()]
    if len(sentences) != len(set(sentences)):
        return True

    return False


# =========================
# Error response
# =========================
def _error_response(job_id: str, message: str, details: str = None) -> dict:
    return {
        "job_id": job_id,
        "status": "failed",
        "error": {
            "message": message,
            "details": details,
        },
    }
