
import os

from fastapi import FastAPI, Header, HTTPException
from app.routers import air

app = FastAPI(
    title="IoT Kampus AIR24 API",
    description="Backend Smart Environment / Air Quality",
    version="1.0.0"
)

app.include_router(air.router)


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "air24-api"
    }


@app.get("/api/v1/test")
def test_api(x_api_key: str = Header(default=None)):
    api_key = os.getenv("API_KEY")

    if not api_key or x_api_key != api_key:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key"
        )

    return {
        "message": "API authentication successful"
    }


@app.get("/api/v1/summary")
def get_summary():
    return {
        "domain": "air",
        "total_rooms": len(air.AIR_ROOMS),
        "status": "initializing"
    }
