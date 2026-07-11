import json
import logging
from typing import Any, AsyncGenerator, Dict, List, Optional
import httpx
from app.core.config import settings

logger = logging.getLogger("sakra.ai.groq")

class GroqClient:
    """Enterprise client for Groq API using HTTPX for low latency and robust streaming."""
    
    def __init__(self):
        self.api_key = settings.GROQ_API_KEY
        self.base_url = "https://api.groq.com/openai/v1/chat/completions"
        self.default_model = "llama-3.3-70b-versatile"

    async def get_response(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send a standard JSON request to Groq."""
        if not self.api_key:
            logger.warning("GROQ_API_KEY is not configured. Falling back to dummy response.")
            return self._dummy_response(messages)

        payload = {
            "model": model or self.default_model,
            "messages": messages,
            "temperature": temperature if temperature is not None else settings.AI_TEMPERATURE,
            "max_tokens": max_tokens or settings.AI_MAX_TOKENS,
        }
        if tools:
            payload["tools"] = tools
        if tool_choice:
            payload["tool_choice"] = tool_choice

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(self.base_url, json=payload, headers=headers)
                if response.status_code != 200:
                    logger.error("Groq API returned error status %d: %s", response.status_code, response.text)
                    return {"choices": [{"message": {"role": "assistant", "content": "I am experiencing temporary API issues. Please try again."}}]}
                return response.json()
        except Exception as e:
            logger.error("Failed to connect to Groq: %s", str(e))
            return {"choices": [{"message": {"role": "assistant", "content": "Failed to connect to the AI copilot service."}}]}

    async def stream_response(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> AsyncGenerator[str, None]:
        """Yield response chunks for streaming UI updates."""
        if not self.api_key:
            yield "GROQ_API_KEY not configured. Private AI finance assistant simulation is active.\n"
            yield "Please check the .env configuration."
            return

        payload = {
            "model": model or self.default_model,
            "messages": messages,
            "temperature": temperature if temperature is not None else settings.AI_TEMPERATURE,
            "max_tokens": max_tokens or settings.AI_MAX_TOKENS,
            "stream": True,
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                async with client.stream("POST", self.base_url, json=payload, headers=headers) as response:
                    if response.status_code != 200:
                        yield f"Error: API returned status {response.status_code}"
                        return
                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        if line.startswith("data: "):
                            data_str = line[6:].strip()
                            if data_str == "[DONE]":
                                break
                            try:
                                chunk = json.loads(data_str)
                                content = chunk.get("choices", [{}])[0].get("delta", {}).get("content", "")
                                if content:
                                    yield content
                            except Exception:
                                continue
        except Exception as e:
            logger.error("Stream failed: %s", str(e))
            yield "Connection error during stream. Please retry."

    def _dummy_response(self, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        last_msg = messages[-1]["content"].lower()
        if "repayment" in last_msg or "100 days" in last_msg:
            content = "Dummy response: रमेश कुमार has the highest overdue amount of ₹45,000, and has crossed the 100 days repayment threshold by 23 days."
        else:
            content = "Dummy Response: Private AI finance assistant ready. Configure your GROQ_API_KEY in backend/.env to activate live intelligent queries."
        return {
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": content
                }
            }]
        }
