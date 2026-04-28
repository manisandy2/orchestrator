from typing import Optional, List, Dict, Any
from datetime import datetime


# class ReviewState:

#     def __init__(self, data: dict):

#         # ========= INPUT =========
#         self.data: Dict[str, Any] = data
#         self.review: str = (data.get("review") or "").strip()
#         self.rating: Optional[int] = data.get("rating")
#         self.reviewer: Optional[str] = data.get("reviewer")
#         self.location_name: Optional[str] = data.get("location_name")
#         self.review_date = data.get("review_date")
#         self.job_id = data.get("job_id")

#         # ========= OUTPUT =========
#         self.draft_response: Optional[str] = None
#         self.final_response: Optional[str] = None

#         # ========= FLOW =========
#         self.next_agent: str = "decision"
#         self.is_complete: bool = False

#         # ========= FLAGS =========
#         self.needs_manual: bool = False
#         self.block_public_reply: bool = False
#         self.issue_type: str = "other"

#         # ========= TRACKING =========
#         self.retry_count: Dict[str, int] = {}
#         self.metrics: Dict[str, dict] = {}

#         # ========= META =========
#         self.created_at: datetime = datetime.utcnow()
#         self.updated_at: datetime = self.created_at
#         self.error: Optional[str] = None

#         # ========= DEBUG =========
#         self.logs: List[Dict] = []
#         self.history: List[Dict] = []

#     # ========= HELPERS =========

#     def log(self, message: str):
#         self.updated_at = datetime.utcnow()
#         self.logs.append({
#             "message": message,
#             "timestamp": self.updated_at.isoformat()
#         })

#     def add_history(self, agent: str, action: str, data: Optional[dict] = None):
#         self.history.append({
#             "agent": agent,
#             "action": action,
#             "data": data or {},
#             "timestamp": datetime.utcnow().isoformat()
#         })

#     def increment_retry(self, agent: str):
#         self.retry_count[agent] = self.retry_count.get(agent, 0) + 1

#     def set_metric(self, agent: str, key: str, value):
#         if agent not in self.metrics:
#             self.metrics[agent] = {}
#         self.metrics[agent][key] = value

#     def set_error(self, error: str):
#         self.error = error
#         self.needs_manual = True
#         self.next_agent = "end"

#     def complete(self):
#         self.is_complete = True
#         self.next_agent = "end"

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

        # ========= AGENT 1 OUTPUT =========
        self.sentiment: Optional[str] = None
        self.issue_type: str = "other"
        self.key_issues: List[str] = []

        self.issues: List[str] = []       # used in pipeline
        self.tone: Optional[str] = None   # used for reply generation

        self.draft_response: Optional[str] = None
        self.complaint_link:Optional[str] = None
        self.response_type: str = "auto"   # auto | manual | blocked
        self.decision_reason: Optional[str] = None
        self.severity: str = "low"         # low | medium | high

        # ========= AGENT 2 OUTPUT =========
        self.final_response: Optional[str] = None
        self.compliance_status: Optional[str] = None  # approved | modified | blocked
        self.compliance_reason: Optional[str] = None
        self.risk_level: str = "low"

        # ========= FLOW =========
        self.next_agent: str = "agent_1"
        self.is_complete: bool = False

        # ========= FLAGS =========
        self.needs_manual: bool = False
        self.block_public_reply: bool = False

        # ========= EVALUATION =========
        self.evaluation: Dict[str, Any] = {}
        self.tone_score: int = 0
        self.brand_voice_score: int = 0
        self.completeness_score: int = 0
        self.overall_score: int = 0

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

    def log(self, message: str,extra: Optional[dict] = None):
        self.updated_at = datetime.utcnow()
        self.logs.append({
            "message": message,
            "extra": extra or {},
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

    def set_tone(self):
        if self.rating is None:
            self.tone = "neutral"
        elif self.rating <= 2:
            self.tone = "empathetic"
        elif self.rating == 3:
            self.tone = "neutral"
        else:
            self.tone = "warm"
            

    def set_final_response(self, reply: Optional[str]):
        if not reply:
            reply = "Thank you for your feedback."
        self.final_response = reply.strip()

    def set_evaluation(self, data: dict):
        self.evaluation = data or {}

        self.tone_score = int(data.get("tone_score", 0))
        self.brand_voice_score = int(data.get("brand_voice_score", 0))
        self.completeness_score = int(data.get("completeness_score", 0))
        self.overall_score = int(data.get("overall_score", 0))

        self.set_metric("evaluation", "overall_score", self.overall_score)

    # =========================
    # FLAGS
    # =========================

    def set_error(self, error: str):
        self.error = error
        self.needs_manual = True
        self.response_type = "manual"
        self.next_agent = "end"

    def mark_manual(self, reason: str):
        self.needs_manual = True
        self.response_type = "manual"
        self.decision_reason = reason

    def block_reply(self, reason: str):
        self.block_public_reply = True
        self.response_type = "blocked"
        self.compliance_status = "blocked"
        self.compliance_reason = reason

    def complete(self):
        self.is_complete = True
        self.next_agent = "end"

    # =========================
    # DEBUG SUMMARY
    # =========================

    def summary(self) -> dict:
        return {
            "job_id": self.job_id,
            "rating": self.rating,
            "tone": self.tone,
            "issue_type": self.issue_type,
            "final_reply": self.final_response,
            "scores": {
                "tone": self.tone_score,
                "brand": self.brand_voice_score,
                "completeness": self.completeness_score,
                "overall": self.overall_score,
            },
            "needs_manual": self.needs_manual,
            "blocked": self.block_public_reply
        }