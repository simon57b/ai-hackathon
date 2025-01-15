import httpx
from typing import Dict, Optional
import os
import json
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    retry=retry_if_exception_type((httpx.RemoteProtocolError, httpx.ReadTimeout, httpx.ConnectTimeout))
)
async def query_model(prompt: str, model: str = "gpt-3.5-turbo-0125", 
                     max_tokens: Optional[int] = None, 
                     temperature: Optional[float] = None) -> Dict:
    """
    Query the OpenAI model with given parameters
    """
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY is not set in environment variables")
        
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
    }
    
    # Only add optional parameters if they are provided
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens
    if temperature is not None:
        payload["temperature"] = temperature
    
    try:
        print(f"Sending request to OpenAI API with payload: {json.dumps(payload, ensure_ascii=False)}")
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            
            # Print response status and headers for debugging
            print(f"OpenAI API Response Status: {response.status_code}")
            print(f"OpenAI API Response Headers: {dict(response.headers)}")
            
            try:
                response.raise_for_status()
                data = response.json()
                print(f"OpenAI API Response Data: {json.dumps(data, ensure_ascii=False)}")
                return data
            except httpx.HTTPStatusError as e:
                error_detail = response.json() if response.content else "No error detail available"
                print(f"HTTP Status Error: {e}, Detail: {error_detail}")
                raise
            except json.JSONDecodeError as e:
                print(f"JSON Decode Error: {e}, Response Text: {response.text}")
                raise
                
    except Exception as e:
        print(f"Error in query_model: {str(e)}")
        print(f"Error type: {type(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        raise 