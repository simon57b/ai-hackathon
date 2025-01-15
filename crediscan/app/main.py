from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import search, model, aggregate

app = FastAPI(title="Crediscan - AI Crawler Application")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(search.router, prefix="/search", tags=["Search"])
app.include_router(model.router, prefix="/model", tags=["Model"])
app.include_router(aggregate.router, prefix="/aggregate", tags=["Aggregate"])

@app.get("/")
async def root():
    return {"message": "Welcome to Crediscan API"} 
