from app.core.config import Settings
from typing import Optional
from urllib.parse import urlencode

settings = Settings()


# def build_complaint_link(ticket_id: str) -> str:
#     if not ticket_id:
#         return None
#     return f"{settings.ANONYMOUS_LINK}?id={ticket_id}"
def build_complaint_link(ticket_id: str) -> Optional[str]:
    """
    Builds a safe complaint link using ticket_id.
    Returns None if invalid.
    """
    if not ticket_id:
        return None

    base_url = getattr(settings, "ANONYMOUS_LINK", None)

    if not base_url:
        return None

    query = urlencode({"id": ticket_id})
    return f"{base_url}?{query}"


# "draft_reply": "Hello Arun Kumar, we sincerely apologize for the disappointing service experience you had at our K.K. Nagar store. Providing a welcoming and helpful environment for our customers is our priority, and it is unfortunate to hear we fell short during your visit. We value your feedback and are always looking for ways to improve. Kindly share more details here: https://stage-customerreview.poorvika.in/anonymous-ticket?id=01KP7RWY7SN56ZY22P7KNB8KET",
# "final_reply": "Hello Arun Kumar, we sincerely apologize for the disappointing service experience you had at our K.K. Nagar store. Providing a welcoming and helpful environment for our customers is our priority, and it is unfortunate to hear your visit did not meet expectations.We value your feedback and are always looking for ways to improve. Kindly share more details here: https://stage-customerreview.poorvika.in/anonymous-ticket?id=01KP7RWY7SN56ZY22P7KNB8KET",


# "draft_reply": "Hello Arun Kumar, we sincerely apologize that your recent experience at our k.k.nagar store did not meet your expectations. We take your feedback regarding our service seriously and always aim to provide a welcoming environment for our customers. We value your input and hope to have the opportunity to serve you better in the future. Kindly share more details here: https://stage-customerreview.poorvika.in/anonymous-ticket?id=01KP7SAKD22SZ5ES4637J3VHAE",
# "final_reply": "Hello Arun Kumar, we sincerely apologize that your recent experience at our K.K. Nagar store did not meet your expectations. We take your feedback regarding our service seriously and always aim to provide a welcoming environment for our customers. We value your input and hope to have the opportunity to serve you better in the future. Kindly share more details here: https://stage-customerreview.poorvika.in/anonymous-ticket?id=01KP7SAKD22SZ5ES4637J3VHAE",


# "draft_reply": "Hello Arun Kumar, we sincerely apologize for the disappointing service you experienced at our k.k.nagar store. We always want our customers to feel valued, and it is concerning to hear that we fell short of those expectations. Your feedback is important to us, and we hope to have the opportunity to serve you much better on your next visit. Kindly share more details here: https://stage-customerreview.poorvika.in/anonymous-ticket?id=01KP7Y8M6K89S6XEJV1R7SGP1N",
# "final_reply": "Hello Arun Kumar, we sincerely apologize for the disappointing service you experienced at our K.K. Nagar store. We always want our customers to feel valued, and it is concerning to hear that we fell short of those expectations. Your feedback is important to us, and we hope to have the opportunity to serve you much better on your next visit. Kindly share more details here: https://stage-customerreview.poorvika.in/anonymous-ticket?id=01KP7Y8M6K89S6XEJV1R7SGP1N",


# "draft_reply": "Hello Arun Kumar, we sincerely apologize for your experience at our k.k.nagar store. It is disappointing to hear that our service did not meet your expectations. We value your feedback and would like to understand more about your visit to help us improve. Kindly share more details here: https://stage-customerreview.poorvika.in/anonymous-ticket?id=01KP7YDXPHE1HK2VCH7HK0KA6Z",
# "final_reply": "Hello Arun Kumar, we sincerely apologize for your experience at our K.K. Nagar store. It is disappointing to hear that our service did not meet your expectations. We value your feedback and would like to understand more about your visit to help us improve. Kindly share more details here: https://stage-customerreview.poorvika.in/anonymous-ticket?id=01KP7YDXPHE1HK2VCH7HK0KA6Z",