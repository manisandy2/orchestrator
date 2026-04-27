import re
import logging

logger = logging.getLogger(__name__)

SENSITIVE_KEYWORDS = re.compile(
    r"\b("
    r"fraud|scam|police|legal|court|case|complaint|fir|"
    r"cheat\w*|harass\w*|abuse\w*"
    r")\b",
    re.IGNORECASE,
)

# =========================
# Sensitive check (word-boundary regex)
# =========================
def _is_sensitive(review: str) -> bool:
    """
    Detect sensitive keywords in customer review.
    Returns True if escalation needed.
    """

    if not review or not review.strip():
        return False
    
    # Normalize text
    text = review.strip().lower()
    match = SENSITIVE_KEYWORDS.search(text)
    
    if match:
        logger.info(f"[SENSITIVE DETECTED] keyword={match.group()}")
        return True
    return False