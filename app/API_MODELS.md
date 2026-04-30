# API Entry Models & Data Reference

This document provides a clear reference for the data models used when interacting with the Multi-Agent Review Orchestrator.

## 1. Direct Review Entry (`/process-review`)

Used for processing a single review submitted directly from a web interface or mobile app.

### Request Body (`ReviewRequest`)

| Field | Type | Required | Description | Example |
| :--- | :--- | :--- | :--- | :--- |
| `comment` | `string` | **Yes** | The actual text of the customer review. | "Great service!" |
| `star_rating` | `int` | **Yes** | Rating (1-5 stars). | `5` |
| `reviewer` | `string` | No | Name of the reviewer. Defaults to "Customer". | "John Doe" |
| `location_name` | `string` | **Yes** | Name of the branch/store. | "Poorvika Mobiles" |
| `review_date` | `string` | No | ISO format date of the review. | "2024-03-27" |

---

## 2. Database Batch Processing (`/process-from-db`)

Used for pulling unreplied reviews directly from the `location_reviews_test` table in PlanetScale.

### Query Parameters

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `location_filter` | `string` | `None` | Exact match for the `name` column in DB. |
| `date_from` | `string` | -30 days | Start date filter (YYYY-MM-DD). |
| `date_to` | `string` | Today | End date filter (YYYY-MM-DD). |
| `max_reviews` | `int` | `50` | Limit for the batch (Max 200). |

---

## 3. Internal Orchestration Contract (`ReviewState`)

Every review, regardless of its entry point, is converted into a `ReviewState` object that travels through the pipeline.

### Input Mapping
- `review`: Maps from `comment`
- `rating`: Maps from `star_rating`
- `job_id`: Generated UUID (or `reviewId` from DB)

### Pipeline Outputs
- `sentiment`: (Agent 1) `positive` | `negative` | `neutral`
- `issue_type`: (Agent 1) e.g., `staff_behavior`, `pricing`, `product_quality`
- `draft_response`: (Agent 1) The first AI draft.
- `final_response`: (Agent 2) The compliance-validated reply.
- `overall_score`: (Evaluation) Quality score from 1-5.

### Database Persistence
All fields from `ReviewState` are permanently archived in the `review_orchestration_state` table in PlanetScale at the end of each run.
