

# =========================
# Error response
# =========================
def _error_response(job_id: str, message: str, details: str = None) -> dict:
    return {
        "job_id": job_id,
        "status": "failed",
        "error": {
            "message": message,
            "details": details,
        },
    }
