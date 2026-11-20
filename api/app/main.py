import os
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from app.auth import AppException
from app.database import now_wib_iso
from app.routers import core, air, energy, coldchain

app = FastAPI(
    title="Mini IoT Platform Kampus - AIR24",
    description="Sistem Terpadu Tiga Domain (Smart Energy, Cold-Chain, Smart Environment) CSEB3073",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS Middleware agar dashboard HTML (port 8080) dapat memanggil API (port 8000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Exception Handler untuk format error seragam sesuai standar Bagian 4.6
@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message
            }
        }
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": str(exc.errors())
            }
        }
    )

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "INTERNAL",
                "message": f"Terjadi kesalahan internal: {str(exc)}"
            }
        }
    )

# Endpoint Wajib: GET /health (Tanpa token API, Bagian 4.6)
@app.get("/health", tags=["Health"])
def health_check():
    return {
        "status": "healthy",
        "waktu": now_wib_iso(),
        "versi": "1.0.0",
        "platform": "Mini IoT Platform Kampus AIR24",
        "wali_integrasi": "Tim 3"
    }

# Register Routers
app.include_router(core.router)
app.include_router(air.router)
app.include_router(energy.router)
app.include_router(coldchain.router)
