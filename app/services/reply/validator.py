from app.core.state import ReviewState
from app.services.reply.utils import SAFE_ESCALATION_REPLY,_is_safe_modification,UNSAFE_PATTERNS
from app.agents.compliance_agent import compliance_agent
import logging


logger = logging.getLogger(__name__)
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