from app.core.config import Settings

settings = Settings()


def build_complaint_link(ticket_id: str) -> str:
    if not ticket_id:
        return ""
    return f"{settings.ANONYMOUS_LINK}?id={ticket_id}"
