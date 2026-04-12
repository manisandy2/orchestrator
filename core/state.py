from typing import Optional, List, Dict, Any
from datetime import datetime


class ReviewState:

    def __init__(self, data: dict):

        # ========= INPUT =========
        self.data: Dict[str, Any] = data
        self.review: str = (data.get("review") or "").strip()
        self.rating: Optional[int] = data.get("rating")
        self.reviewer: Optional[str] = data.get("reviewer")
        self.location_name: Optional[str] = data.get("location_name")
        self.review_date = data.get("review_date")
        self.job_id = data.get("job_id")

        # ========= OUTPUT =========
        self.draft_response: Optional[str] = None
        self.final_response: Optional[str] = None

        # ========= FLOW =========
        self.next_agent: str = "decision"
        self.is_complete: bool = False

        # ========= FLAGS =========
        self.needs_manual: bool = False
        self.block_public_reply: bool = False
        self.issue_type: str = "other"

        # ========= TRACKING =========
        self.retry_count: Dict[str, int] = {}
        self.metrics: Dict[str, dict] = {}

        # ========= META =========
        self.created_at: datetime = datetime.utcnow()
        self.updated_at: datetime = self.created_at
        self.error: Optional[str] = None

        # ========= DEBUG =========
        self.logs: List[Dict] = []
        self.history: List[Dict] = []

    # ========= HELPERS =========

    def log(self, message: str):
        self.updated_at = datetime.utcnow()
        self.logs.append({
            "message": message,
            "timestamp": self.updated_at.isoformat()
        })

    def add_history(self, agent: str, action: str, data: Optional[dict] = None):
        self.history.append({
            "agent": agent,
            "action": action,
            "data": data or {},
            "timestamp": datetime.utcnow().isoformat()
        })

    def increment_retry(self, agent: str):
        self.retry_count[agent] = self.retry_count.get(agent, 0) + 1

    def set_metric(self, agent: str, key: str, value):
        if agent not in self.metrics:
            self.metrics[agent] = {}
        self.metrics[agent][key] = value

    def set_error(self, error: str):
        self.error = error
        self.needs_manual = True
        self.next_agent = "end"

    def complete(self):
        self.is_complete = True
        self.next_agent = "end"
