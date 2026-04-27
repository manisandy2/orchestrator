
def get_tone(rating: int) -> str:
    if rating <= 2:
        return "empathetic"
    elif rating == 3:
        return "neutral"
    else:
        return "warm"