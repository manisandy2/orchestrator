import asyncio
import json
import time
import logging
import re
from typing import Union
from google import genai
from app.core.config import Settings

logger = logging.getLogger(__name__)
settings = Settings()

client = genai.Client(api_key=settings.GEMINI_API_KEY)

def extract_json(text: str) -> Union[dict, list]:
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(r"(\{.*\}|\[.*\])", text, re.DOTALL)
    if not match:
        raise ValueError("No JSON found")

    return json.loads(match.group())


async def call_gemini(
    prompt: str,
    agent_name: str = "unknown",
    trace_id: str = "no-trace",
    retries: int = 3,
    base_timeout: int = 30,
    expect_json: bool = False,
) -> dict:

    start_time = time.time()

    logger.info(f"[{trace_id}] [{agent_name}] Gemini call started")

    for attempt in range(retries):
        try:
            timeout = base_timeout + (attempt * 15)

            # Using native async client
            response = await asyncio.wait_for(
                client.aio.models.generate_content(
                    model=settings.GEMINI_MODEL,
                    contents=[prompt],
                ),
                timeout=timeout
            )

            if not response or not getattr(response, "text", None):
                raise ValueError("Empty response")

            content = response.text.strip()

            # ✅ JSON parsing (VERY IMPORTANT)
            if expect_json:
                try:
                    content = extract_json(content)
                except Exception as e:
                    raise ValueError(f"Invalid JSON: {e}")

            latency = round(time.time() - start_time, 2)

            logger.info(
                f"[{trace_id}] [{agent_name}] Success | "
                f"Attempt: {attempt+1} | Latency: {latency}s"
            )

            return {
                "status": "success",
                "content": content,
                "latency": latency,
                "attempt": attempt + 1,
            }

        except asyncio.TimeoutError:
            logger.warning(f"[{trace_id}] Timeout on attempt {attempt + 1}")

        except Exception as e:
            logger.warning(f"[{trace_id}] Error on attempt {attempt + 1}: {e}")

        if attempt < retries - 1:
            await asyncio.sleep(2 ** attempt)

    latency = round(time.time() - start_time, 2)

    logger.error(f"[{trace_id}] Gemini failed after retries")

    return {
        "status": "failed",
        "reason": "llm_unavailable",
        "content": fallback_response(agent_name, expect_json=expect_json),
        "latency": latency,
    }


def fallback_response(agent_name: str, expect_json: bool = False) -> Union[str, dict]:
    msg = "We are experiencing delays. Please try again later."
    if agent_name == "review_agent":
        msg = "We appreciate your feedback and will review this internally."
    elif agent_name == "compliance_agent":
        msg = "Please raise a support ticket for further assistance."

    return {"error": msg} if expect_json else msg