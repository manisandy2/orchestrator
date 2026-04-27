import asyncio
import json
import logging
from datetime import date
from typing import Dict,Any,Optional
 
import httpx
 
from app.core.config import Settings
 
settings = Settings()
logger = logging.getLogger(__name__)
 
 
def _build_headers() -> dict:
    return {
        "platform": "web",
        "Authorization": f"App {settings.CRM_AUTH_KEY}",
    }
 
 
def _build_enquiry_payload(location_name: str) -> dict:
    return {
        "cusId": "",
        "billNo": "",
        "enquiryFor": "Complaints",
        "mobileNo": settings.DEFAULT_MOBILE,
        "branchName": location_name,
        "subCategory": "Google Review",
        "callType": 0,
    }
 
 
def _build_complaint_payload(
    location_name: str,
    reviewer_name: str,
    review_date: date,
    review_text: str,
) -> dict:
    return {
        "cusId": "",
        "party": [],
        "billNo": "",
        "enquiryFor": "Complaints",
        "itemName": "",
        "billDate": "",
        "customerName": reviewer_name,
        "productName": "",
        "branchName": location_name,
        "mobileNo": settings.DEFAULT_MOBILE,
        "subCategory": "Google Review",
        "complainType": "google_auto_review",
        "callType": 0,
        "documentDate": review_date.isoformat(),
        "itemModelName": "",
        "itemBrandName": "",
        "invoiceAmount": "0",
        "complainAbout": "Others",
        "complainSource": "Google Review",
        "complainRecieveDate": review_date.isoformat(),
        "complaintantExpectation": str(review_text)[:300] if review_text else "",
        "complaintantAdvocateDetails": {},
    }

# def _extract_ticket_id(response: dict) -> Optional[str]:
#     return (
#         response.get("data", {})
#         .get("complainAndEnquirySaved", {})
#         .get("complain", {})
#         .get("id")
#     )
def _extract_ticket_id(response: dict) -> Optional[str]:
    try:
        data = response.get("data") or {}
        complain_saved = data.get("complainAndEnquirySaved") or {}
        complain = complain_saved.get("complain") or {}

        ticket_id = complain.get("id")

        if not ticket_id:
            logger.warning(f"⚠️ Ticket ID missing. Response: {response}")

        return ticket_id

    except Exception as e:
        logger.error(f"❌ Error extracting ticket id: {e}")
        logger.debug(f"Full response: {response}")
        return None

 
async def create_complaint(
    location_name: str,
    reviewer_name: str,
    review_date: date,
    review_text: str,
    job_id: Optional[str] = None,
    url: str = None,
    retries: int = 3,
) -> dict:
    url = url or settings.STAGE_URL
    headers = _build_headers()

    files = {
        "enquiry": (None, json.dumps(_build_enquiry_payload(location_name))),
        "complain": (None, json.dumps(_build_complaint_payload(
            location_name, reviewer_name, review_date, review_text
        ))),
    }
    
    timeout_config = httpx.Timeout(10.0, connect=5.0)
    async with httpx.AsyncClient(timeout=timeout_config) as client:

        for attempt in range(retries):
            try:
                logger.info(f"[{job_id}] CRM attempt {attempt+1}")

                response = await client.post(url, headers=headers, files=files)
                response.raise_for_status()

                try:
                    data = response.json()
                except Exception:
                    logger.error(f"[{job_id}] Invalid JSON response")
                    raise ValueError("Invalid CRM response format")

                ticket_id = _extract_ticket_id(data)

                if not ticket_id:
                    logger.error(
                        f"[{job_id}] Missing ticket_id",
                        extra={"response": data}
                    )
                    return {
                        "status": "failed",
                        "message": "Missing ticket_id",
                        "data": data
                    }

                logger.info(f"[{job_id}] Complaint created: {ticket_id}")

                return {
                    "status": "created",
                    "ticket_id": ticket_id,
                    "data": data,
                }

            except httpx.HTTPStatusError as e:
                logger.error(
                    f"[{job_id}] HTTP {e.response.status_code}",
                    extra={"body": e.response.text}
                )

            except httpx.RequestError as e:
                logger.error(f"[{job_id}] Network error: {repr(e)}")

            except Exception:
                logger.exception(f"[{job_id}] Unexpected CRM error")

            # exponential backoff
            if attempt < retries - 1:
                await asyncio.sleep(2 ** attempt)

    logger.error(f"[{job_id}] Complaint failed after {retries} retries")

    return {
        "status": "failed",
        "message": "Complaint creation failed after retries"
    }