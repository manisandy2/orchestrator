import httpx
import logging
import json
from app.core.config import Settings

settings = Settings()
logger = logging.getLogger(__name__)

CRM_URL = settings.STAGE_URL


class CRMErrorCodes:
    SUCCESS = "SUCCESS"
    AUTH_ERROR = "AUTH_ERROR"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    SERVER_ERROR = "SERVER_ERROR"
    TIMEOUT = "TIMEOUT"
    NETWORK_ERROR = "NETWORK_ERROR"
    INVALID_RESPONSE = "INVALID_RESPONSE"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"


async def complaint_agent(data):
    print("Creating complaint ##############################################")
    headers = {
        "platform": "web",
        "Authorization": f"App {settings.CRM_AUTH_KEY}",
    }

    enquiry_payload = {
        "cusId": "",
        "billNo": "",
        "enquiryFor": "Complaints",
        "mobileNo": "0",
        "branchName": data['location_name'],
        "subCategory": "Google Review",
        "callType": 0
    }

    complain_payload = {
        "cusId": "",
        "party": [],
        "billNo": "",
        "enquiryFor": "Complaints",
        "itemName": "",
        "billDate": "",
        "customerName": data['reviewer'],
        "productName": "",
        "branchName": data['location_name'],
        "mobileNo": "0",
        "subCategory": "Google Review",
        "complainType": "google_auto_review",
        "callType": 0,
        "documentDate": data['review_date'],
        "itemModelName": "",
        "itemBrandName": "",
        "invoiceAmount": "0",
        "complainAbout": "Others",
        "complainSource": "Google Review",
        "complainRecieveDate": data['review_date'],
        "complaintantExpectation": data['review'],
        "complaintantAdvocateDetails": {}
    }

    files = {
        "enquiry": (None, json.dumps(enquiry_payload)),
        "complain": (None, json.dumps(complain_payload)),
    }

    try:
        async with httpx.AsyncClient(timeout=settings.HTTP_TIMEOUT) as client:
            response = await client.post(CRM_URL, headers=headers, files=files)

            # ✅ Handle HTTP errors explicitly
            if response.status_code == 401:
                return {
                    "status": "failed",
                    "error_code": CRMErrorCodes.AUTH_ERROR,
                    "message": "Authorization failed",
                    "details": response.text
                }

            if response.status_code == 400:
                return {
                    "status": "failed",
                    "error_code": CRMErrorCodes.VALIDATION_ERROR,
                    "message": "Validation error from CRM",
                    "details": response.text
                }

            if response.status_code >= 500:
                return {
                    "status": "failed",
                    "error_code": CRMErrorCodes.SERVER_ERROR,
                    "message": "CRM server error",
                    "details": response.text
                }

            response.raise_for_status()

            # ✅ Safe JSON parsing
            try:
                result = response.json()
            except Exception:
                return {
                    "status": "failed",
                    "error_code": CRMErrorCodes.INVALID_RESPONSE,
                    "message": "Invalid JSON response from CRM",
                    "details": response.text
                }

            # logger.info(f"CRM response: {result}")

            complain_data = result.get("data", {}) \
                .get("complainAndEnquirySaved", {}) \
                .get("complain", {})

            complaint_id = complain_data.get("id")

            if not complaint_id:
                return {
                    "status": "failed",
                    "error_code": CRMErrorCodes.INVALID_RESPONSE,
                    "message": "Ticket ID missing in CRM response",
                    "details": result
                }

            return {
                "status": "created",
                "ticket_id": complaint_id,
                "error_code": CRMErrorCodes.SUCCESS
            }

    except httpx.TimeoutException:
        logger.error("CRM timeout error")
        return {
            "status": "failed",
            "error_code": CRMErrorCodes.TIMEOUT,
            "message": "Request timed out"
        }

    except httpx.RequestError as e:
        logger.error(f"Network error: {str(e)}")
        return {
            "status": "failed",
            "error_code": CRMErrorCodes.NETWORK_ERROR,
            "message": "Network error while calling CRM",
            "details": str(e)
        }

    except Exception as e:
        logger.exception("Unexpected CRM error")
        return {
            "status": "failed",
            "error_code": CRMErrorCodes.UNKNOWN_ERROR,
            "message": "Unexpected error",
            "details": str(e)
        }