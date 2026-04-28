


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



SAFE_ESCALATION_REPLY = (
    "We take this matter seriously. Kindly share more details "
    "through the provided link so we can investigate further."
)

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


UNSAFE_PATTERNS = [
    "we admit",
    "our mistake",
    "we were wrong",
    "staff was wrong",
    "it was our fault",
    "we take full responsibility"
]