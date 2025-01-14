from fastapi import APIRouter, HTTPException
from app.utils.serper import search_serper

router = APIRouter()

@router.get("/")
async def search(query: str):
    try:
        results = await search_serper(query)
        return {"query": query, "results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 