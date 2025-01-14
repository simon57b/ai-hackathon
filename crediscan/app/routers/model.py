from fastapi import APIRouter, HTTPException
from app.utils.model_api import query_model
from pydantic import BaseModel

router = APIRouter()

class ModelQuery(BaseModel):
    prompt: str
    model: str

@router.post("/")
async def process_model_query(query: ModelQuery):
    try:
        response = await query_model(query.prompt, query.model)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 