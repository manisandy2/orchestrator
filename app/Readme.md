# Orchestrator - Multi-Agent Review Processing System

A scalable multi-agent orchestration system designed to process customer reviews, classify sentiment, extract issues, generate responses, and ensure brand compliance.

## 🧠 Architecture Overview

This system uses a 2-agent architecture managed by a central orchestrator:

User Input → Orchestrator → Agent 01 → Agent 02 → Final Output
---
## 🤖 Agents
🟢 Agent 01 — Decision + Draft Generator

Responsibilities:

Sentiment classification (Positive / Neutral / Negative)
Issue type detection
Extract up to 3 key issues
Generate draft response
🔵 Agent 02 — Supervisor / Compliance Validator

Responsibilities:

Validate response tone and structure
Apply brand rules
Fix or reject unsafe responses
Produce final response
🧩 Core Components
📦 ReviewState (Shared Contract)

All agents communicate using a central state object defined in `app/core/state.py`. This object tracks the evolution of the review from ingestion to final response.

```python
class ReviewState:
    def __init__(self, data: dict):
        self.review = data.get("review")
        self.rating = data.get("rating")
        self.job_id = data.get("job_id")
        
        # Agent Outputs
        self.sentiment = None
        self.issue_type = "other"
        self.draft_response = None
        self.final_response = None
        self.compliance_status = "pending"
```

🧠 Orchestrator

The `Orchestrator` controls the sequential execution flow between agents.

```python
async def process_review_task(input_data: dict):
    state = ReviewState(input_data)
    
    # 1. Decision Agent
    # 2. CRM Complaint Creation
    # 3. Reply Generation
    # 4. Compliance Check
    # 5. Database Archive
```
⚙️ Features
✅ Sentiment Analysis
✅ Issue Extraction (max 3 issues)
✅ AI Draft Response Generation
✅ Brand Compliance Validation
✅ Async Processing Support
✅ Structured Logging
✅ Scalable Agent Architecture
🔄 Workflow
User submits review
Orchestrator initializes ReviewState
Agent 01 processes:
sentiment
issues
draft response
Agent 02 validates:
tone
compliance
final response
Final output returned
📡 API Example
Request
POST /process-review

{
  "comment": "Very bad service, delayed response",
  "star_rating": 1,
  "reviewer": "Mani",
  "location_name": "Anna Nagar",
  "review_date": "2024-01-01"
}
Response
{
  "data": {
    "sentiment": "negative",
    "issues": ["delay", "service quality"],
    "final_response": "We sincerely apologize for the delay..."
  }
}
🛠️ Installation
git clone https://github.com/manisandy2/orchestrator.git
cd orchestrator

pip install -r requirements.txt
▶️ Run Project
uvicorn app.main:app --reload
🧪 Testing
pytest
📈 Future Improvements
🔁 Retry & fallback mechanism
📊 Observability (logs + metrics)
🧵 Queue-based processing (Celery / Kafka)
🧠 Memory-enabled agents
🔐 Role-based access control
🌐 Multi-language support
⚠️ Current Limitations
No strict retry handling
Limited validation rules
No distributed queue support
👨‍💻 Author

Manikandan R.
Backend Developer | Python | Django | AI Systems