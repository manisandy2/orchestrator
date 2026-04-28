

def _blocked_response(job_id: str, review: str = "", rating: int = None, location_name: str = "") -> dict:
    return {
        "job_id": job_id,
        "status": "completed",

        "input": {
            "review": review,
            "rating": rating,
            "location_name": location_name,
        },

        "agent_1": None,

        "agent_2": {
            "status": "blocked",
            "draft_reply": None,
            "final_reply": (
                "We’re sorry to hear about your experience. "
                "For privacy and safety reasons, we’re unable to address this here. "
                "Please contact our support team with more details so we can assist you further."
            ),
            "compliance_flags": ["sensitive"],
            "blocked_reason": "Sensitive content detected via _is_sensitive() rule",
            "modified": False
        },

        "meta": {
            "needs_manual": True,
            "escalation_reason": "sensitive_content",
            "complaint_link": None
        }
    }