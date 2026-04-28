from app.core.state import ReviewState
from app.agents.reply_agent import reply_agent
from app.services.reply.utils import _is_bad_reply

async def _generate_reply(state: ReviewState) -> str:
    state.log("Reply generation started")
    max_retries = 2

    for attempt in range(max_retries):
        try:
            state.increment_retry("reply")
            state.log(f"Reply attempt {attempt + 1}")

            reply = await reply_agent(
                review=state.review,
                rating=state.rating,
                reviewer=state.reviewer,
                store=state.location_name,
                issue_type=state.issue_type,
                tone=state.tone,
                issues=state.issues,
                complaint_link=state.complaint_link
            )

            if reply and isinstance(reply, str):
                reply = reply.strip()
                if not _is_bad_reply(reply, state.rating):
                    state.log("Reply generated successfully")
                    state.set_metric("reply", "success", True)
                    return reply
                state.log("Reply failed quality check, retrying")

        except Exception as e:
            state.log(f"Reply attempt {attempt + 1} failed: {e}")
            if attempt == max_retries - 1:
                state.set_metric("reply", "error", str(e))

    # Fallback
    state.log("Using fallback reply")
    fallback = (
        "We're sorry for your experience. Please share more details so we can assist you."
        if state.rating and state.rating <= 2
        else "Thank you for your feedback. We will look into this."
    )
    state.add_history("reply", "fallback", fallback)
    state.set_metric("reply", "fallback_used", True)
    return fallback