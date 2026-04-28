import logging
from typing import Optional

from app.services.gemini_service import call_gemini
from app.prompts.reply_prompt import REPLY_PROMPT

logger = logging.getLogger(__name__)


# =========================
# Prompt Builder
# =========================
def _build_prompt(
    review: str,
    rating: int,
    reviewer: str,
    store: str,
    issue_type: str,
    tone: str,
    issues: list,
    complaint_link: Optional[str],
) -> str:
    review = " ".join((review or "").strip().split())
    instruction = f"- Include this support link: {complaint_link}" if complaint_link else ""

    return REPLY_PROMPT.format(
        reviewer=reviewer or "Customer",
        store=store or "our store",
        rating=rating,
        review=review,
        issue_type=issue_type,
        tone=tone or "neutral",
        issues=issues or [],
        complaint_instruction=instruction,
    )

def validate_reply(reply: str) -> None:
    if not reply:
        raise ValueError("Reply is empty")

    if len(reply.split()) < 10:
        raise ValueError("Reply too short")

    banned_phrases = [
        "i don't know",
        "not my job",
        "no idea",
    ]

    lower_reply = reply.lower()

    if any(p in lower_reply for p in banned_phrases):
        raise ValueError("Unsafe reply detected")


# =========================
# Fallback Reply
# =========================
def _fallback_reply(rating: int, store: str, complaint_link: Optional[str] = None) -> str:
    store = store or "our store"

    if rating >= 4:
        return (
            f"Thank you for your feedback! We're glad you had a great experience at {store}. "
            "We look forward to serving you again."
        )
    if rating <= 2:
        base = (
            f"We're sorry to hear about your experience at {store}. "
            "We truly understand your concern and are working to make things right."
        )
        if complaint_link:
            base += f" You can reach us here: {complaint_link}"
        return base

    return (
        f"Thank you for your feedback. We appreciate your input and will continue "
        f"to improve our services at {store}."
    )


# =========================
# Reply Agent
# =========================
async def reply_agent(
    review: str,
    rating: int,
    reviewer: str,
    store: str,
    issue_type: str = "other",
    tone: str = "neutral",
    issues: Optional[list] = None,
    complaint_link: Optional[str] = None,
) -> str:

    prompt = _build_prompt(
        review,
        rating,
        reviewer,
        store,
        issue_type,
        tone,
        issues,
        complaint_link,
    )

    max_retries = 2

    for attempt in range(max_retries):
        try:
            logger.info(f"Reply attempt {attempt + 1}")

            llm_result = await call_gemini(prompt, agent_name="reply_agent")

            if llm_result.get("status") != "success":
                raise ValueError("LLM failed")

            reply = llm_result.get("content", "").strip()

            validate_reply(reply)

            return reply

        except Exception as e:
            logger.warning(f"Attempt {attempt + 1} failed: {e}")

            if attempt == max_retries - 1:
                logger.error("Using fallback reply")
                return _fallback_reply(rating, store, complaint_link)
