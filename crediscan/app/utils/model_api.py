import httpx
from typing import Dict
import os
import json
import asyncio
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    retry=retry_if_exception_type((httpx.ReadTimeout, httpx.ConnectTimeout, httpx.RequestError)),
    reraise=True
)
async def query_model(prompt: str, model: str = "gpt-3.5-turbo-0125", max_tokens: int = 4000) -> Dict:
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0.7
    }
    
    # print(f"Request payload: {json.dumps(payload, indent=2)}")
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            # print(f"Response status: {response.status_code}")
            # print(f"Response headers: {dict(response.headers)}")
            # print(f"Response body: {response.text}")
            
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        print(f"HTTP Status Error: {e.response.status_code}")
        print(f"Error response: {e.response.text}")
        raise
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        raise 