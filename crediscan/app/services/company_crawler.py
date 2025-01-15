import os
from typing import Dict, Any, List, Set
import httpx
import json
import asyncio
from urllib.parse import urljoin, urlparse
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
from crawl4ai.extraction_strategy import LLMExtractionStrategy
from ..models import CompanyInfo

class CompanyAnalyzer:
    # common positions for AI and Web3 companies
    COMMON_POSITIONS = [
        # Engineering Positions
        "Software Engineer", "Senior Software Engineer", "Full Stack Engineer",
        "Backend Engineer", "Frontend Engineer", "DevOps Engineer",
        "Machine Learning Engineer", "AI Engineer", "Data Engineer",
        "Blockchain Engineer", "Smart Contract Developer", "Protocol Engineer",
        "Site Reliability Engineer", "Infrastructure Engineer",
        
        # AI/ML Positions
        "AI Researcher", "Machine Learning Scientist", "Data Scientist",
        "NLP Engineer", "Computer Vision Engineer", "AI Product Manager",
        "Research Scientist", "Applied Scientist",
        
        # Web3/Blockchain Positions
        "Blockchain Developer", "Solidity Developer", "Web3 Engineer",
        "DeFi Engineer", "Token Economics Researcher", "Crypto Research Analyst",
        "Smart Contract Auditor", "Web3 Security Engineer",
        
        # Product & Design
        "Product Manager", "Product Designer", "UX Designer",
        "UI Designer", "Technical Product Manager", "Product Owner",
        
        # Management & Leadership
        "Engineering Manager", "Technical Lead", "CTO",
        "VP of Engineering", "Director of Engineering",
        "Head of AI", "Head of Blockchain", "Technical Director",
        
        # Business & Operations
        "Business Development", "Operations Manager",
        "Community Manager", "Growth Manager", "Technical Writer",
        "Developer Advocate", "Developer Relations",
        
        # Security & QA
        "Security Engineer", "QA Engineer", "Test Engineer",
        "Security Researcher", "Penetration Tester",
        
        # Data Roles
        "Data Analyst", "Analytics Engineer", "Business Intelligence Analyst",
        "Data Architect", "Database Engineer",
        
        # Research & Innovation
        "Research Engineer", "Innovation Lead", "Technical Researcher",
        "Cryptography Researcher", "Protocol Researcher"
    ]

    def merge_lists(self, data_list: List[Dict], key: str) -> List:
        """merge list fields, handle possible dictionary items"""
        result = []
        seen = set()
        for data in data_list:
            if not data.get(key):
                continue
            for item in data[key]:
                if isinstance(item, dict):
                    item_str = json.dumps(item, sort_keys=True)
                    if item_str not in seen:
                        seen.add(item_str)
                        result.append(item)
                else:
                    item_str = str(item)
                    if item_str not in seen:
                        seen.add(item_str)
                        result.append(item)
        return result

    def merge_security_assessments(self, data_list: List[Dict]) -> Dict:
        """merge security assessment data"""
        merged = {}
        for data in data_list:
            if not data.get("security_assessment"):
                continue
            for k, v in data["security_assessment"].items():
                if k not in merged:
                    merged[k] = v
                elif isinstance(v, dict):
                    if isinstance(merged[k], dict):
                        merged[k].update(v)
                else:
                    merged[k] = v
        return merged

    def normalize_url(self, url: str) -> str:
        """normalize URL format"""
        parsed = urlparse(url)
        # remove www prefix, ensure URL format consistent
        netloc = parsed.netloc.replace('www.', '')
        # remove trailing slash
        return f"{parsed.scheme}://{netloc}{parsed.path.rstrip('/')}".lower()

    async def verify_with_get(self, url: str, client: httpx.AsyncClient) -> bool:
        """deep verification with GET request"""
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            }
            response = await client.get(url, headers=headers)
            if response.status_code in [200, 304, 301, 302]:
                content_text = response.text.lower()
                error_markers = [
                    "404", "not found", "page not found",
                    "doesn't exist", "does not exist",
                    "error 404", "404 error",
                    "page could not be found",
                    "page isn't available",
                    "page no longer exists",
                    "page has been removed",
                    "sorry, we couldn't find that page",
                    "page you're looking for isn't here"
                ]
                if not any(marker in content_text for marker in error_markers):
                    return True
                else:
                    print(f"Page contains error markers: {url}")
            return False
        except Exception as e:
            print(f"GET verification failed for {url}: {e}")
            return False

    async def get_valid_urls(self, base_url: str) -> Set[str]:
        """get valid URLs"""
        paths = ["", "about", "about-us", "team", "our-team", "company", 
                "solution", "contact", "how-it-works", "features",
                "careers", "jobs", "cases"]
        valid_urls = set()
        base_url = self.normalize_url(base_url)
        
        urls_to_check = [urljoin(base_url, path) for path in paths]
        
        async with httpx.AsyncClient(
            follow_redirects=True, 
            timeout=10.0,
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
        ) as client:
            async def check_url(url: str):
                try:
                    headers = {
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    }
                    response = await client.head(url, headers=headers)
                    
                    if response.status_code == 200:
                        # HEAD request successful
                        final_url = str(response.url)
                        normalized_url = self.normalize_url(final_url)
                        if normalized_url not in valid_urls:
                            valid_urls.add(normalized_url)
                            print(f"Found valid URL (HEAD 200): {url}")
                    elif response.status_code in [403, 405, 404, 301, 302, 304]:
                        # for these status codes, try GET request verification
                        print(f"HEAD request returned {response.status_code}, trying GET for: {url}")
                        if await self.verify_with_get(url, client):
                            normalized_url = self.normalize_url(url)
                            if normalized_url not in valid_urls:
                                valid_urls.add(normalized_url)
                                print(f"Found valid URL (GET after HEAD {response.status_code}): {url}")
                    else:
                        print(f"Skipping URL (HEAD {response.status_code}): {url}")
                        
                except httpx.HTTPError:
                    # HEAD request failed, try GET request
                    print(f"HEAD request failed, trying GET for: {url}")
                    if await self.verify_with_get(url, client):
                        normalized_url = self.normalize_url(url)
                        if normalized_url not in valid_urls:
                            valid_urls.add(normalized_url)
                            print(f"Found valid URL (GET after HEAD failed): {url}")
                except Exception as e:
                    print(f"Error checking URL {url}: {e}")

            # first check base URL
            await check_url(base_url)
            if not valid_urls:
                print(f"Base URL {base_url} is not accessible")
                return valid_urls

            # concurrently check other paths
            tasks = [check_url(url) for url in urls_to_check if url != base_url]
            await asyncio.gather(*tasks)

            return valid_urls

    async def analyze_company(self, base_url: str) -> CompanyInfo:
        try:
            llm_strat = LLMExtractionStrategy(
                provider="openai/gpt-4o",
                api_token=os.getenv('OPENAI_API_KEY'),
                schema=CompanyInfo.schema_json(),
                extraction_type="schema",
                instruction=f"""
                You are an expert analyst specializing in company research. Analyze all the provided content from multiple pages and extract:
                1. Company background and history
                2. Founders' information and their backgrounds
                3. Funding rounds and investment details
                4. Legal issues and disputes
                5. Security risks and vulnerabilities
                6. User reviews and feedback
                7. Job positions - For any careers or jobs pages:
                   - Extract ONLY the job titles from current job openings
                   - Focus especially on these common positions in AI and Web3 companies:
                     {json.dumps(self.COMMON_POSITIONS, indent=2)}
                   - Match job titles against the common positions list when possible
                   - Include other positions if they are clearly stated
                   - Return just the list of job titles, no additional details needed
                
                For job positions, ensure you:
                - Look for exact or similar matches to the common positions list
                - Include any unique positions specific to the company
                - Normalize titles to standard formats when possible
                - Remove duplicates
                - Only include current openings
                
                Return the information in the specified JSON schema format. For job_positions,
                return a simple array of strings containing only the job titles.
                """
            )

            print(f"Starting crawl for base URL: {base_url}")
            crawl_config = CrawlerRunConfig(
                extraction_strategy=llm_strat,
                exclude_external_links=True,
                cache_mode=CacheMode.BYPASS
            )
            
            # get valid URLs
            valid_urls = await self.get_valid_urls(base_url)
            if not valid_urls:
                raise Exception("No valid URLs found to crawl")

            all_extracted_data = []
            
            async with AsyncWebCrawler(config=BrowserConfig(
                headless=True,
                extra_args=[
                    "--disable-gpu",
                    "--disable-dev-shm-usage",
                    "--no-sandbox",
                    "--disable-blink-features=AutomationControlled",
                    '--no-first-run',
                    '--no-zygote',
                    '--single-process',
                    '--incognito',
                    '--user-data-dir=/tmp/temp-chrome-profile',
                    '--disable-extensions',
                    '--disable-background-networking',
                    '--disable-default-apps',
                    '--disable-sync',
                    '--disable-translate',
                    '--metrics-recording-only',
                    '--safebrowsing-disable-auto-update',
                    '--password-store=basic',
                    '--remote-debugging-port=9222'
                ]
            )) as crawler:
                await crawler.start()
                try:
                    session_id = "session1"

                    for url in valid_urls:
                        try:
                            print(f"Crawling URL: {url}")
                            result = await crawler.arun(
                                url=url,
                                config=crawl_config,
                                session_id=session_id
                            )
                            if result and result.success and result.extracted_content:
                                print(f"Successfully crawled: {url}")
                                extracted_data = result.extracted_content
                                if isinstance(extracted_data, str):
                                    extracted_data = json.loads(extracted_data)
                                if isinstance(extracted_data, list) and extracted_data:
                                    extracted_data = extracted_data[0]
                                if isinstance(extracted_data, dict):
                                    all_extracted_data.append(extracted_data)
                                    print(f"Added data from {url}")
                        except Exception as e:
                            print(f"Error processing {url}: {e}")
                            continue

                    if all_extracted_data:
                        # extract all job titles
                        all_jobs = set()  # use set to automatically deduplicate
                        for data in all_extracted_data:
                            if isinstance(data, dict) and "job_positions" in data:
                                jobs = data.get("job_positions", [])
                                if isinstance(jobs, list):
                                    all_jobs.update(str(job) for job in jobs if job)

                        merged_data = {
                            "company_name": next((data.get("company_name") for data in all_extracted_data if data.get("company_name")), "Unknown"),
                            "website": base_url,
                            "background": "\n".join(filter(None, [data.get("background") for data in all_extracted_data])),
                            "founders": self.merge_lists(all_extracted_data, "founders"),
                            "funding": self.merge_lists(all_extracted_data, "funding"),
                            "legal_issues": self.merge_lists(all_extracted_data, "legal_issues"),
                            "security_assessment": self.merge_security_assessments(all_extracted_data),
                            "user_reviews": self.merge_lists(all_extracted_data, "user_reviews"),
                            "overall_summary": "\n".join(filter(None, [data.get("overall_summary") for data in all_extracted_data])),
                            "job_positions": sorted(list(all_jobs))  # convert back to list and sort
                        }
                        return CompanyInfo(**merged_data)
                    else:
                        raise Exception("No content was successfully extracted")
                finally:
                    await crawler.close()
            
        except Exception as e:
            print(f"Error during company analysis: {e}")
            return CompanyInfo(
                company_name="Unknown",
                website=base_url,
                background="Information not available",
                founders=[],
                funding=[],
                legal_issues=[],
                security_assessment={},
                user_reviews=[],
                overall_summary=f"Failed to analyze company: {str(e)}",
                job_positions=[]
            ) 
