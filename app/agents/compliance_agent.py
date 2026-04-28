import json
import logging
import re
from typing import Dict,Optional
from app.services.gemini_service import call_gemini
from app.prompts.compliance_prompt import COMPLIANCE_PROMPT

logger = logging.getLogger(__name__)

SAFE_ESCALATION_REPLY = (
    "We take this matter seriously. Kindly share more details "
    "through the provided link so we can investigate further."
)

SENSITIVE_ISSUE_TYPES = {"fraud", "harassment", "hygiene"}

SENSITIVE_KEYWORDS = {
    "fraud", "scam", "harass", "abuse", "police", "legal", "court"
}
VALID_STATUSES = {"approved", "modified", "blocked"}

# =========================
# Fallback (keep simple)
# =========================
def get_fallback_reply(
    rating: int,
    mode: str = "reply",
) -> str:

    if mode == "compliance":
        return SAFE_ESCALATION_REPLY

    if rating >= 4:
        return "Thank you for your feedback! We're glad you had a great experience."

    if rating <= 2:
        return "We're sorry for your experience. We will work to improve."

    return "Thank you for your feedback. We will continue to improve."


# =========================
# Compliance Agent (Agent 2)
# =========================
async def compliance_agent(
    review: str,
    rating: int,
    draft_reply: str,
    issue_type: str,
) -> dict:

    try:
        if not draft_reply:
            return {
                "status": "approved",
                "final_reply": get_fallback_reply(rating, mode="reply"),
                "reason": "Empty draft — generic fallback used",
            }
        
        review_lower = (review or "").lower()

        # ── Rule-based overrides (run before LLM) ──────────────────────
        # Fraud / harassment / hygiene → force escalation ticket, no public reply
        if issue_type in SENSITIVE_ISSUE_TYPES:
            return {
                "status": "blocked",
                "final_reply": SAFE_ESCALATION_REPLY,
                "reason": "Sensitive issue",
            }

        # Secondary safety net: check review text directly for sensitive language
        
        if any(kw in review_lower for kw in SENSITIVE_KEYWORDS):
            return {
                "status": "blocked",
                "final_reply": SAFE_ESCALATION_REPLY,
                "reason": "Sensitive keywords detected",
            }

        # Staff issue → safe wording, no public admission of fault
        if issue_type == "staff":
            return {
                "status": "modified",
                "final_reply": (
                    "We will investigate the matter in detail. "
                    "Please share more information through the support link."
                ),
                "reason": "Staff issue",
            }


        prompt = f"""
            {COMPLIANCE_PROMPT}

            Review: "{review}"
            Issue Type: "{issue_type}"
            Draft Reply: "{draft_reply}"
            """

        result = await call_gemini(prompt, agent_name="compliance_agent", expect_json=True)

        if not result or result.get("status") != "success":
            raise ValueError("Compliance LLM failed")

        parsed = result.get("content",{})

        if not isinstance(parsed, dict):
            raise ValueError("Invalid JSON from compliance LLM")

        status = parsed.get("status", "approved")
        final_reply = parsed.get("final_reply") or draft_reply
        reason = parsed.get("reason", "")

        if status not in VALID_STATUSES:
            status = "approved"

        if status == "blocked":
            final_reply = SAFE_ESCALATION_REPLY

        if status == "modified":
            if not final_reply or len(final_reply.split()) < 5:
                return {
                    "status": "blocked",
                    "final_reply": SAFE_ESCALATION_REPLY,
                    "reason": "Invalid modified reply",
                }

        if status == "approved" and not final_reply:
            final_reply = draft_reply

        return {
            "status": status,
            "final_reply": final_reply,
            "reason": reason,
        }

    except Exception as e:
        logger.exception(f"Compliance agent error: {e}")

        return {
            "status": "blocked",
            "final_reply": get_fallback_reply(rating, mode="compliance"),
            "reason": "Compliance failure",
        }


