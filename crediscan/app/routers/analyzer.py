from fastapi import APIRouter, HTTPException
from pydantic import HttpUrl
from ..services.company_crawler import CompanyAnalyzer
from ..models import CompanyInfo
from ..utils.cache_manager import CacheManager

router = APIRouter()
company_analyzer = CompanyAnalyzer()
analyzer_cache = CacheManager("analyzer_result.json")

@router.post("/analyze")
async def analyze_company(url: HttpUrl):
    """
    Analyze a company based on the provided URL.
    The AI crawler will extract company information, background, founders,
    funding, legal issues, security risks, and user reviews.
    """
    try:
        # check cache
        params = {"url": str(url)}
        cached_result = analyzer_cache.get_cached_result(params)
        if cached_result:
            return CompanyInfo(**cached_result["result"])

        # if no cache, execute analysis
        result = await company_analyzer.analyze_company(str(url))
        
        # save result to cache
        analyzer_cache.save_result(params, result.dict())
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 