from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os

# ensure environment variables are loaded when app starts
load_dotenv()

# validate critical environment variables
required_env_vars = ['SERPER_API_KEY', 'OPENAI_API_KEY', 'AGGREGATE_TOKENS']
for var in required_env_vars:
    if not os.getenv(var):
        print(f"Warning: {var} environment variable is not set")

# import router instances directly
from app.routers.search import router as search_router
from app.routers.model import router as model_router
from app.routers.aggregate import router as aggregate_router
from app.routers.analyzer import router as analyzer_router
from app.routers.discover import router as discover_router

app = FastAPI(title="Crediscan - AI Crawler Application")

# configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# register routers
app.include_router(search_router, prefix="/search", tags=["Search"])
app.include_router(model_router, prefix="/model", tags=["Model"])
app.include_router(aggregate_router, prefix="/aggregate", tags=["Aggregate"])
app.include_router(analyzer_router, prefix="/analyzer", tags=["Analyzer"])
app.include_router(discover_router, prefix="/discover", tags=["Discover"])

@app.get("/")
async def root():
    return {"message": "Welcome to Crediscan API"} 