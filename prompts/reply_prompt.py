from app.prompts.base_prompt import BASE_PROMPT

REPLY_PROMPT = BASE_PROMPT + """

TASK:
Write a professional customer reply.

INPUT:
- Review: "{review}"
- Rating: {rating}
- Issue Type: "{issue_type}"
- Reviewer: "{reviewer}"
- Store: "{store}"

RULES:
- Single paragraph
- 3–4 sentences
- Clear, natural, and human tone
- No markdown
- No "Dear"
- No signature or closing line
- Do NOT over-apologize
- Do NOT repeat sentences or phrases
- Do NOT mention investigation, escalation, or internal processes
- Do NOT mention tickets, links, or complaint systems


BEHAVIOR:
- Positive → thank the customer and appreciate their feedback
- Neutral → acknowledge feedback and show attentiveness
- Negative → express concern and willingness to look into the issue (no commitments)

STRICT RULES:
- Do NOT promise resolution, refund, or action
- Do NOT assume details not mentioned in the review
- Do NOT admit staff fault directly
- Keep response under 80 words

QUALITY RULES:
- If rating <= 2 → must include an apology or empathy
- If review is very short or unclear → keep reply generic and polite
- Avoid overly generic responses; include slight context when possible
- Reference the issue briefly if mentioned
- Use reviewer/store name naturally only if it fits the sentence

STRUCTURE:
1. Acknowledge feedback
2. Address concern or appreciation
3. Close with a polite, neutral statement

TONE:
- Calm, respectful, and brand-safe
- Avoid robotic or repetitive phrases

{complaint_instruction}
"""