def validate_tone(reply: str, tone: str) -> bool:
    """
    Ensures reply tone matches expected tone.
    """
    
    if not reply:
        return False

    text = reply.lower()

    if tone == "empathetic":
        # must show apology or understanding
        keywords = ["sorry", "apolog", "understand", "regret"]
        return any(word in text for word in keywords)

    elif tone == "warm":
        # must show appreciation
        keywords = ["thank", "glad", "happy", "great"]
        return any(word in text for word in keywords)

    elif tone == "neutral":
        # should not be too emotional (basic check)
        # allow simple acknowledgment
        keywords = ["thank", "appreciate", "noted"]
        return any(word in text for word in keywords) or len(text) > 20

    return True

def validate_completeness(reply: str, issues: list) -> bool:
    if not reply:
        return False

    # If no issues → it's okay to be generic
    if not issues:
        return True

    text = reply.lower()

    # Normalize issues (handle phrases)
    normalized_issues = [issue.lower().strip() for issue in issues if issue]

    # Check if at least one issue is referenced
    for issue in normalized_issues:
        # handle partial match (e.g., "staff behavior" → "staff")
        words = issue.split()
        if any(word in text for word in words):
            return True

    return False