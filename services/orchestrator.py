import asyncio
import logging
import re
from typing import Optional

from app.agents.reply_agent import reply_agent
from app.tools.crm_tool import complaint_agent
from app.agents.supervisor_agent import decision_agent, compliance_agent
from app.utility.helper import build_complaint_link
from app.core.state import ReviewState

logger = logging.getLogger(__name__)

SAFE_ESCALATION_REPLY = (
    "We take this matter seriously. Kindly share more details "
    "through the provided link so we can investigate further."
)

SENSITIVE_KEYWORDS = re.compile(
    r"\b(fraud|scam|police|legal|court|cheating|harassment|abuse)\b",
    re.IGNORECASE,
)


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

        state.add_history("decision", "completed", decision)
        state.set_metric("decision", "success", True)
        state.issue_type = decision.get("classification", {}).get("issue_type", "other")

        # Flag for manual review on low confidence or missing data
        confidence = decision.get("confidence", 0.9)
        if confidence < 0.6 or not state.review:
            state.needs_manual = True

        # =========================
        # STEP 2 + 3: Complaint & reply (parallel)
        # =========================
        complaint_task = (
            _safe_create_complaint(state)
            if decision.get("create_ticket")
            else asyncio.sleep(0, result=None)
        )

        complaint_link, reply = await asyncio.gather(
            complaint_task,
            _generate_reply(state),
        )

        if not reply:
            reply = "Thank you for your feedback. We will look into this."

        # =========================
        # STEP 4: Attach complaint link
        # =========================
        if complaint_link:
            state.draft_response = f"{reply} Kindly share more details here: {complaint_link}"
        else:
            state.draft_response = reply

        # =========================
        # STEP 5: Clean reply
        # =========================
        state.draft_response = _clean_reply(state.draft_response)

        # =========================
        # STEP 6: Compliance agent
        # =========================
        final_reply = await _validate_reply(state)
        state.final_response = final_reply
        state.set_metric("validation", "completed", True)

        logger.info(f"[{job_id}] Processing complete")

        return {
            "job_id": job_id,
            "status": "success",
            "type": "complaint_and_reply" if complaint_link else "reply",
            "complaint_link": complaint_link,
            "reply": state.final_response,
            "needs_manual": state.needs_manual,
            "decision": decision,
            "logs": state.logs,
            "history": state.history,
        }

    except Exception as e:
        logger.exception(f"[{job_id}] Processing failed")
        state.set_error(str(e))
        return _error_response(job_id=job_id, message="Processing failed", details=str(e))


# =========================
# Sensitive check (word-boundary regex)
# =========================
def _is_sensitive(review: str) -> bool:
    if not review:
        return False
    return bool(SENSITIVE_KEYWORDS.search(review))


def _blocked_response(job_id: str) -> dict:
    return {
        "job_id": job_id,
        "status": "success",
        "type": "blocked",
        "reply": "We request you to raise a ticket so our team can assist you further.",
        "decision": {},
    }


# =========================
# Reply deduplication
# =========================
def _clean_reply(text: str) -> str:
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

    for attempt in range(max_retries):
        try:
            state.increment_retry("complaint")
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

    state.log("Complaint creation failed after retries")
    state.add_history("complaint", "failed")
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
async def _validate_reply(state: ReviewState) -> str:
    state.log("Validation started")

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

        if status == "approved":
            state.log("Reply approved")
            state.add_history("validation", "approved", {"reply": state.draft_response, "reason": reason})
            return state.draft_response

        if status == "modified" and final_reply:
            if not _is_safe_modification(state.draft_response, final_reply):
                state.log("Modification too large — keeping original draft")
                state.add_history("validation", "forced_approved", {"reason": "modification_too_large"})
                return state.draft_response
            state.log("Reply modified by compliance")
            state.add_history("validation", "modified", {
                "original": state.draft_response,
                "modified": final_reply,
                "reason": reason,
            })
            return final_reply

        if status == "blocked":
            state.log("Reply blocked by compliance")
            state.add_history("validation", "blocked", {"reason": reason})
            return "We request you to raise a ticket so our team can assist you further."

        # Unknown status — safe fallback
        state.log(f"Unknown compliance status '{status}' — using draft")
        return state.draft_response

    except Exception as e:
        logger.exception(f"Validation error: {e}")
        state.log(f"Validation failed: {e}")
        state.add_history("validation", "error", {"error": str(e)})
        return state.draft_response


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
