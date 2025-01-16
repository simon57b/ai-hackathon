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
import traceback
import asyncio

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
    """Optimize content translation using GPT with minimal API calls"""
    try:
        # 1. Clean and prepare content
        paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]
        if not paragraphs:
            return ""
        
        # 2. Combine paragraphs into chunks to minimize API calls
        # 减小输入块大小到2000字符，但保持较大的输出token限制
        MAX_CHARS_PER_CHUNK = 1000  # 减小输入块大小
        chunks = []
        current_chunk = []
        current_length = 0
        
        for para in paragraphs:
            para_length = len(para)
            if current_length + para_length > MAX_CHARS_PER_CHUNK:
                if current_chunk:
                    chunks.append('\n\n'.join(current_chunk))
                current_chunk = [para]
                current_length = para_length
            else:
                current_chunk.append(para)
                current_length += para_length
        
        if current_chunk:
            chunks.append('\n\n'.join(current_chunk))
        
        # 3. Process each chunk with a single API call
        translated_chunks = []
        for i, chunk in enumerate(chunks):
            print(f"\nProcessing chunk {i+1}/{len(chunks)} (length: {len(chunk)})")
            print(f"Chunk content preview: {chunk[:100]}...")
            
            prompt = f"""Translate the following Chinese text to English.
Requirements:
- Keep the translation complete and accurate
- Maintain all original formatting and structure
- Keep technical terms, names, and numbers unchanged
- Make it professional and natural

Text to translate:
{chunk}"""
            
            try:
                response = await query_model(
                    prompt=prompt,
                    model="gpt-3.5-turbo-0125",
                    max_tokens=4000,  # 保持较大的输出token限制
                    temperature=0.3
                )
                
                if (response and 
                    isinstance(response, dict) and 
                    'choices' in response and 
                    len(response['choices']) > 0 and 
                    'message' in response['choices'][0] and 
                    'content' in response['choices'][0]['message']):
                    
                    translated_content = response['choices'][0]['message']['content']
                    print(f"Successfully translated chunk {i+1}. Preview: {translated_content[:100]}...")
                    translated_chunks.append(translated_content.strip())
                else:
                    print(f"Warning: Invalid response format for chunk {i+1}: {json.dumps(response, ensure_ascii=False)}")
                    translated_chunks.append(chunk)
                    
            except Exception as e:
                print(f"Error translating chunk {i+1}: {str(e)}")
                print(f"Full error details: {traceback.format_exc()}")
                await asyncio.sleep(5)
                translated_chunks.append(chunk)
        
        # 4. Combine all translated chunks
        result = '\n\n'.join(translated_chunks)
        print(f"Translation completed. Total chunks: {len(chunks)}, Final length: {len(result)}")
        return result
        
    except Exception as e:
        print(f"Error in translate_and_optimize: {str(e)}")
        print(f"Full error details: {traceback.format_exc()}")
        return content  # Return original content if translation fails

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
                "content": f"介绍 {company_name} 这家属于 web3 行业还是 AI 行业公司的业务和背景，创始人资料和背景，融资情况，法律纠纷，安全风险评估以及用户评价"
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