from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, HttpUrl
from typing import List, Optional, Dict, Any, Tuple
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig
from crawl4ai.extraction_strategy import LLMExtractionStrategy
import json
import os
from ..services.company_crawler import CompanyAnalyzer
from ..models import CompanyInfo
from ..utils.serper import search_serper
import asyncio
from ..utils.cache_manager import CacheManager

# create the router instance
router = APIRouter()
discover_cache = CacheManager("discover_result.json")

# define the request and response models
class DiscoverRequest(BaseModel):
    urls: List[HttpUrl] = ["https://www.ycombinator.com/companies/industry/crypto-web3", "https://startups.gallery/categories/industries/web3", "https://wellfound.com/startups/industry/web3-4"]
    max_companies: Optional[int] = 30
    
    def dict(self, *args, **kwargs):
        """override dict method to ensure HttpUrl is correctly serialized"""
        d = super().dict(*args, **kwargs)
        d['urls'] = [str(url) for url in d['urls']]  # convert HttpUrl to string
        return d

class CompanyListItem(BaseModel):
    company_name: str
    website_url: Optional[str]
    job_positions: Optional[List[str]] = []

class DiscoverResponse(BaseModel):
    discovered_companies: List[CompanyInfo]
    failed_companies: List[CompanyListItem]

async def get_company_website(company_name: str) -> Optional[str]:
    """use Google search to get company official website"""
    try:
        print(f"Searching for website of: {company_name}")
        search_results = await search_serper(f"{company_name} ai web3 official website")
        
        if search_results and "organic" in search_results:
            for result in search_results["organic"]:
                if "link" in result:
                    print(f"Found website for {company_name}: {result['link']}")
                    return result["link"]
        
        print(f"No website found for {company_name}")
        return None
    except Exception as e:
        print(f"Error searching website for {company_name}: {e}")
        return None

def parse_llm_response(content: Any, max_companies: int) -> List[CompanyListItem]:
    """Parse and validate LLM response"""
    print(f"Parsing LLM response: {json.dumps(content, indent=2)}")
    
    companies = []
    try:
        if isinstance(content, str):
            content = json.loads(content)
        
        if isinstance(content, list):
            # use max_companies in request to limit processing
            for item in content[:max_companies]:
                try:
                    if isinstance(item, dict):
                        if 'content' in item and isinstance(item['content'], list):
                            company_name = item['content'][0]
                            # extract job positions
                            job_positions = item.get('jobs', [])
                            if company_name:
                                companies.append(CompanyListItem(
                                    company_name=company_name,
                                    website_url=None,
                                    job_positions=job_positions
                                ))
                except Exception as e:
                    print(f"Error parsing company item {item}: {e}")
                    continue
                
        print(f"Successfully parsed {len(companies)} companies")
        return companies
    except Exception as e:
        print(f"Error parsing content: {e}")
        return []

async def extract_companies_and_jobs(url: str, max_companies: int) -> List[CompanyListItem]:
    """Use LLM crawler to extract company list and job positions"""
    print(f"\nStarting company extraction from: {url}")
    
    llm_strat = LLMExtractionStrategy(
        provider="openai/gpt-4o",
        api_token=os.getenv('OPENAI_API_KEY'),
        extraction_type="list",
        instruction=f"""
        Extract a list of companies and their job positions from this page.
        For each company, provide:
        1. The company name
        2. A list of their current job positions (if available)
        
        Return the results as a list of JSON objects with this format:
        {{
            "index": number,
            "tags": ["company"],
            "content": [company_name],
            "jobs": [list of job positions]  // Optional field
        }}
        
        Focus only on actual companies and their job listings mentioned on the page.
        Limit the extraction to the first {max_companies} companies found.
        """
    )

    crawl_config = CrawlerRunConfig(
        extraction_strategy=llm_strat,
        exclude_external_links=True
        # wait_until="networkidle"
    )

    browser_config = BrowserConfig(
        headless=True,
        extra_args=[
            "--disable-gpu",
            "--disable-dev-shm-usage",
            "--no-sandbox",
            "--disable-blink-features=AutomationControlled"
        ]
    )

    async with AsyncWebCrawler(config=browser_config) as crawler:
        await crawler.start()
        try:
            print(f"Crawling URL: {url}")
            result = await crawler.arun(url=url, config=crawl_config)
            
            if result and result.success and result.extracted_content:
                print("Successfully extracted content")
                companies = parse_llm_response(result.extracted_content, max_companies)
                print(f"Extracted companies: {[company.company_name for company in companies]}")
                
                # concurrent get all company websites
                async def get_websites():
                    tasks = [get_company_website(company.company_name) for company in companies]
                    websites = await asyncio.gather(*tasks)
                    for company, website in zip(companies, websites):
                        company.website_url = website
                
                await get_websites()
                return companies
            else:
                print(f"No content extracted from {url}")
                return []
        finally:
            await crawler.close()

async def analyze_companies_concurrently(companies: List[CompanyListItem], 
                                      company_analyzer: CompanyAnalyzer) -> Tuple[List[CompanyInfo], List[CompanyListItem]]:
    """concurrently analyze multiple companies"""
    discovered = []
    failed = []
    
    async def analyze_single_company(company: CompanyListItem):
        try:
            if not company.website_url:
                return None
            
            print(f"Analyzing {company.company_name} at {company.website_url}")
            company_info = await company_analyzer.analyze_company(company.website_url)
            if company_info:
                # add job positions to CompanyInfo object
                company_info.job_positions = company.job_positions
                return company_info
        except Exception as e:
            print(f"Error analyzing {company.company_name}: {e}")
            return None
    
    # concurrently execute all analysis tasks
    tasks = [analyze_single_company(company) for company in companies]
    results = await asyncio.gather(*tasks)
    
    # process results
    for company, result in zip(companies, results):
        if result:
            discovered.append(result)
        else:
            failed.append(company)
    
    return discovered, failed

@router.post("/", response_model=DiscoverResponse)
async def discover_companies(request: DiscoverRequest):
    """Discover and analyze companies"""
    try:
        # check cache
        params = request.dict()
        cached_result = discover_cache.get_cached_result(params)
        if cached_result:
            return DiscoverResponse(**cached_result["result"])

        # if no cache, execute discovery
        print(f"\nStarting company discovery for {len(request.urls)} URLs")
        company_analyzer = CompanyAnalyzer()
        
        # concurrently process all URLs, pass max_companies parameter
        all_companies = []
        tasks = [extract_companies_and_jobs(str(url), request.max_companies) for url in request.urls]
        companies_lists = await asyncio.gather(*tasks)
        
        for companies in companies_lists:
            all_companies.extend(companies)

        if not all_companies:
            return DiscoverResponse(discovered_companies=[], failed_companies=[])

        # ensure total does not exceed max_companies in request
        companies_to_process = all_companies[:request.max_companies]
        print(f"\nProcessing {len(companies_to_process)} companies (max: {request.max_companies})")
        
        # concurrently analyze all companies
        discovered_companies, failed_companies = await analyze_companies_concurrently(
            companies_to_process, 
            company_analyzer
        )

        print(f"\nDiscovery complete. Found: {len(discovered_companies)}, Failed: {len(failed_companies)}")
        result = DiscoverResponse(
            discovered_companies=discovered_companies,
            failed_companies=failed_companies
        )
        
        # save result to cache
        discover_cache.save_result(params, result.dict())
        
        return result
    except Exception as e:
        print(f"Error in discover_companies: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error discovering companies: {str(e)}"
        ) 