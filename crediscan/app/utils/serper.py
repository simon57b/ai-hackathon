import httpx
from typing import Dict
import os

SERPER_API_KEY = os.getenv("SERPER_API_KEY")

async def search_serper(query: str) -> Dict:
    url = "https://google.serper.dev/search"
    headers = {"X-API-KEY": SERPER_API_KEY}
    payload = {"q": query}
    
    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        return response.json() 