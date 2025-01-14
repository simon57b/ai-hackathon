from pydantic import BaseModel
from typing import List, Dict, Optional

class CompanyInfo(BaseModel):
    company_name: str
    website: Optional[str] = None
    background: str
    founders: List[Dict]
    funding: List[Dict]
    legal_issues: List[Dict]
    security_assessment: Dict
    user_reviews: List[Dict]
    overall_summary: str
    job_positions: List[str] = []