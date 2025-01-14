import random
import json
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import httpx
from typing import List, Optional
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import re
from ..utils.model_api import query_model
from ..utils.cache_manager import CacheManager
import os

router = APIRouter()
aggregate_cache = CacheManager("aggregate_result.json")

# define the request model
class AggregateQuery(BaseModel):
    company_name: str
    model: str = "research"

# define the response model
class AggregateResponse(BaseModel):
    content: str

# 从环境变量获取 tokens
def get_tokens() -> List[str]:
    tokens_str = os.getenv("AGGREGATE_TOKENS", "")
    if not tokens_str:
        raise ValueError("AGGREGATE_TOKENS environment variable is not set")
    return [token.strip() for token in tokens_str.split(",") if token.strip()]

def clean_content(content: str) -> str:
    """remove the text and links containing specific keywords"""
    lines = content.split('\n')
    cleaned_lines = [line for line in lines if 'metaso' not in line.lower()]
    
    content = '\n'.join(cleaned_lines)
    content = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', 
                    lambda x: '' if 'metaso' in x.group().lower() else x.group(), 
                    content)
    
    return content

async def translate_and_optimize(content: str) -> str:
    """use the OpenAI API to translate and optimize the content, process long text by paragraphs"""
    # split the content by paragraphs
    paragraphs = content.split('\n\n')
    translated_paragraphs = []
    
    for paragraph in paragraphs:
        if not paragraph.strip():
            continue
            
        prompt = f"""
        Please translate the following Chinese text to English and optimize it. 
        Maintain all original Markdown formatting and structure.
        Make the translation professional and natural while preserving all factual information.
        
        Text to translate:
        {paragraph}
        """
        
        try:
            response = await query_model(
                prompt=prompt,
                model="gpt-3.5-turbo-0125",
                max_tokens=4000
            )
            if response and 'choices' in response:
                translated_content = response['choices'][0]['message']['content']
                translated_paragraphs.append(translated_content.strip())
            else:
                raise ValueError("Invalid response from OpenAI API")
        except Exception as e:
            print(f"Translation error for paragraph: {e}")
            # if translation fails, keep the original text
            translated_paragraphs.append(paragraph)
    
    # merge all translated paragraphs
    return '\n\n'.join(translated_paragraphs)

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    retry=retry_if_exception_type((httpx.ReadTimeout, httpx.ConnectTimeout, httpx.RequestError)),
    reraise=True
)
async def get_company_info(company_name: str, model: str) -> str:
    """call the third-party api to get the company info"""
    tokens = get_tokens()
    if not tokens:
        raise ValueError("No valid tokens available")
        
    token = random.choice(tokens)
    url = "http://localhost:8000/v1/chat/completions"
    print(f"Using metaso token: {token}")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    
    payload = {
        "model": model,
        "messages": [
            {
                "role": "assistant",
                "content": f"{company_name} 的公司业务和背景，创始人资料和背景，融资情况，法律纠纷，安全风险评估以及用户评价"
            }
        ],
        "stream": False
    }

    print(f"Calling third-party API for {company_name}")
    # print(f"Request payload: {json.dumps(payload, indent=2, ensure_ascii=False)}")

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(url, json=payload, headers=headers)
        print(f"Raw response content: {response.text}")
        response.raise_for_status()
        data = response.json()
        print(f"Parsed response data: {json.dumps(data, indent=2, ensure_ascii=False)}")
        
        if 'choices' in data and len(data['choices']) > 0:
            if 'message' in data['choices'][0] and 'content' in data['choices'][0]['message']:
                content = data['choices'][0]['message']['content']
            else:
                content = data['choices'][0].get('content')
                
            if content:
                cleaned_content = clean_content(content)
                # translate to english and optimize the content
                translated_content = await translate_and_optimize(cleaned_content)
                return translated_content
            else:
                raise ValueError("Content field is empty in the response")
        else:
            raise ValueError(f"Invalid response format: {json.dumps(data, indent=2)}")

@router.post("/")
async def aggregate_data(query: AggregateQuery) -> AggregateResponse:
    try:
        # check cache
        params = query.dict()
        cached_result = aggregate_cache.get_cached_result(params)
        if cached_result:
            return AggregateResponse(content=cached_result["result"]["content"])

        # if no cache, execute query
        print(f"Starting aggregate_data for company: {query.company_name}")
        content = await get_company_info(query.company_name, query.model)
        
        # save result to cache
        result = {"content": content}
        aggregate_cache.save_result(params, result)
        
        return AggregateResponse(content=content)
    except Exception as e:
        print(f"Error in aggregate_data: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error processing request: {str(e)}"
        ) 