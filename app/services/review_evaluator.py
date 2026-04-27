import json
import logging
import re
from app.services.gemini_service import call_gemini
from app.prompts.evaluation_prompt import EVALUATION_PROMPT

logger = logging.getLogger(__name__)

def _extract_json(text: str) -> dict:
    try:
        # Extract JSON block using regex
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return json.loads(match.group())
    except Exception:
        pass
    return None

async def evaluate_reply(review: str, rating: int, reply: str) -> dict:
    prompt = EVALUATION_PROMPT.format(
        review=review,
        rating=rating,
        reply=reply
    )

    try:
        res = await call_gemini(
            prompt,
            agent_name="evaluation",
            expect_json=True)
        
        if res.get("status") != "success":
            return _fallback("llm_failed", rating)

        
        data = res.get("content")

        if not isinstance(data, dict):
            return _fallback("invalid_json", rating)
        

        return {
            "tone_score": int(data.get("tone_score", 3)),
            "brand_voice_score": int(data.get("brand_voice_score", 3)),
            "completeness_score": int(data.get("completeness_score", 2)),
            "overall_score": int(data.get("overall_score", 3)),
            "issues": data.get("issues", []),
            "suggestions": data.get("suggestions", [])
        }

    except Exception as e:
        logger.exception("Evaluation failed")
        return _fallback(str(e))


def _fallback(reason: str, rating: int = None):
    # Smart default scores based on rating

    return {
        "tone_score": 2 if rating and rating <= 2 else 3,
        "brand_voice_score": 3,
        "completeness_score": 2,
        "overall_score": 3,
        "issues": [reason],
        "suggestions": ["evaluation fallback used"]
    }