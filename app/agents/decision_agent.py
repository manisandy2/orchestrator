from typing import Dict
from app.prompts.decision_prompt import DECISION_AGENT_PROMPT
from app.services.gemini_service import call_gemini
from app.schemas.supervisor import SupervisorResponse
import logging
from pydantic import ValidationError

logger = logging.getLogger(__name__)
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