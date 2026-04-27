import json
import logging
import re
from typing import Dict

from pydantic import ValidationError

from app.services.gemini_service import call_gemini
from app.schemas.supervisor import SupervisorResponse
from app.prompts.decision_prompt import DECISION_AGENT_PROMPT
from app.prompts.compliance_prompt import COMPLIANCE_PROMPT

logger = logging.getLogger(__name__)

SAFE_ESCALATION_REPLY = (
    "We take this matter seriously. Kindly share more details "
    "through the provided link so we can investigate further."
)

SENSITIVE_ISSUE_TYPES = {"fraud", "harassment", "hygiene"}


# =========================
# JSON Parser
# =========================
def _parse_json(text: str) -> Dict | list | None:
    if not text:
        return None

    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Fallback: extract first JSON block
    match = re.search(r"(\{.*?\}|\[.*?\])", text, re.DOTALL)
    if not match:
        return None

    try:
        return json.loads(match.group())
    except json.JSONDecodeError:
        return None


# =========================
# Fallback Decision
# =========================
# def _fallback_decision(review: str, rating: int, reviewer: str, store: str) -> Dict:
#     name = reviewer or "Customer"
#     store_name = store or "our store"

#     if rating >= 4:
#         response = (
#             f"Hi {name}, thank you for your positive feedback about {store_name}. "
#             "We're glad you had a great experience and look forward to serving you again."
#         )
#     elif rating == 3:
#         response = (
#             f"Hi {name}, thank you for your feedback about {store_name}. "
#             "We appreciate your input and will use it to improve our service."
#         )
#     else:
#         response = (
#             f"Hi {name}, we're sorry to hear about your experience at {store_name}. "
#             "Please share more details so we can look into this and assist you further."
#         )

#     return {
#         "classification": {
#             "sentiment": "positive" if rating >= 4 else ("neutral" if rating == 3 else "negative"),
#             "issue_type": "other",
#             "rating": rating,
#         },
#         "issues": [],
#         "severity": "high" if rating <= 1 else ("medium" if rating == 2 else "low"),
#         "action": "complaint" if rating <= 2 else "reply",
#         "create_ticket": rating <= 2,
#         "response": response,
#         "reason": "fallback",
#         "confidence": 0.5,
#     }

def _fallback_decision(review: str, rating: int, reviewer: str, store: str) -> Dict:

    if rating >= 4:
        response = "Thank you for your feedback. We're glad you had a positive experience."

    elif rating == 3:
        response = "Thank you for your feedback. We appreciate you sharing your experience."

    else:
        response = "Sorry to hear about your experience. Thank you for bringing this to our attention."

    return {
        "classification": {
            "sentiment": "positive" if rating >= 4 else ("neutral" if rating == 3 else "negative"),
            "issue_type": "other",
            "rating": rating,
        },
        "issues": [],
        "severity": "high" if rating <= 1 else ("medium" if rating == 2 else "low"),
        "action": "complaint" if rating <= 2 else "reply",
        "create_ticket": rating <= 2,
        "response": response,
        "reason": "fallback",
        "confidence": 0.5,
    }


# =========================
# Decision Agent (Agent 1)
# =========================
async def decision_agent(
    review: str,
    rating: int,
    reviewer: str = "anonymous",
    store: str = "unknown",
) -> Dict:

    try:
        review = " ".join((review or "").strip().split())[:1000]
        safe_review = review.replace("{", "{{").replace("}", "}}")

        prompt = DECISION_AGENT_PROMPT.format_map({
            "review": safe_review,
            "rating": rating,
            "reviewer": reviewer,
            "store": store,         # matches {store} in prompt
        })

        llm_result = await call_gemini(prompt, agent_name="decision_agent", expect_json=True)

        if not llm_result or llm_result.get("status") != "success":
            raise ValueError("LLM failed")

        parsed = llm_result.get("content", {})
        if not parsed or not isinstance(parsed, dict):
            raise ValueError("Invalid JSON from LLM")

        validated = SupervisorResponse(**parsed)
        data = validated.model_dump()

        # data["issues"] = data.get("issues") or []
        data["confidence"] = float(data.get("confidence", 0.9))
        data["issues"] = _clean_issues(data.get("issues"))
        classification = data.get("classification", {})

        data["classification"] = {
            "sentiment": classification.get("sentiment", "neutral"),
            "issue_type": classification.get("issue_type", "other"),
            "rating": rating,
        }

        logger.info(
            f"Decision agent: action={data.get('action')} "
            f"ticket={data.get('create_ticket')} "
            f"confidence={data.get('confidence')}"
        )

        return data

    except (ValidationError, ValueError) as e:
        logger.warning(f"Decision agent validation error: {e}")
    except Exception as e:
        logger.exception(f"Decision agent error: {e}")

    return _fallback_decision(review or "", rating, reviewer, store)

def _clean_issues(issues):
    if not isinstance(issues, list):
        return []

    cleaned = []
    for issue in issues:
        if isinstance(issue, str) and len(issue.strip()) > 2:
            cleaned.append(issue.strip().lower())

    return cleaned[:3]

# =========================
# Compliance Agent (Agent 2)
# =========================
async def compliance_agent(
    review: str,
    rating: int,
    draft_reply: str,
    issue_type: str,
    reviewer: str = "anonymous",
    store: str = "unknown",
) -> dict:

    ESCALATION_RESPONSE = {
        "status": "blocked",
        "final_reply": SAFE_ESCALATION_REPLY,
        "reason": "Sensitive issue — escalation required",
    }

    try:
        if not draft_reply:
            return {
                "status": "approved",
                "final_reply": "Thank you for your feedback. We will look into this.",
                "reason": "Empty draft — generic fallback used",
            }

        # ── Rule-based overrides (run before LLM) ──────────────────────
        # Fraud / harassment / hygiene → force escalation ticket, no public reply
        if issue_type in SENSITIVE_ISSUE_TYPES:
            return ESCALATION_RESPONSE

        # Secondary safety net: check review text directly for sensitive language
        sensitive_keywords = {"fraud", "scam", "harass", "abuse", "police", "legal", "court"}
        if any(kw in (review or "").lower() for kw in sensitive_keywords):
            return ESCALATION_RESPONSE

        # Staff issue → safe wording, no public admission of fault
        if issue_type == "staff":
            safe_reply = "We will investigate the matter in detail. Please share more information in the ticket below."
            return {
                "status": "modified",
                "final_reply": safe_reply,
                "reason": "Staff issue — public admission avoided",
            }

        # ── LLM validation (secondary) ──────────────────────────────────
        # prompt = COMPLIANCE_PROMPT.format_map({
        #     "review": review,
        #     "issue_type": issue_type,
        #     "draft_reply": draft_reply,
        # })
        prompt = f"""
            {COMPLIANCE_PROMPT}

            Review: "{review}"
            Issue Type: "{issue_type}"
            Draft Reply: "{draft_reply}"
            """

        result = await call_gemini(prompt, agent_name="compliance_agent", expect_json=True)

        if not result or result.get("status") != "success":
            raise ValueError("Compliance LLM failed")

        parsed = result.get("content")
        if not isinstance(parsed, dict):
            raise ValueError("Invalid JSON from compliance LLM")

        status = parsed.get("status", "approved")
        final_reply = parsed.get("final_reply", draft_reply)
        reason = parsed.get("reason", "")

        # Guard: blocked reply must always carry the standard safe message
        if status == "blocked":
            final_reply = SAFE_ESCALATION_REPLY

        # Guard: approved reply must not be empty
        if status == "approved" and not final_reply:
            final_reply = draft_reply

        return {
            "status": status,
            "final_reply": final_reply,
            "reason": reason,
        }

    except Exception as e:
        logger.exception(f"Compliance agent error: {e}")
        raise
