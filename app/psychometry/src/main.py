# app/psychometry/src/main.py

"""
Psychometry Service - Main entry point.
"""
import logging
import sys
from pathlib import Path

# Добавляем /app в PYTHONPATH для импорта
sys.path.insert(0, '/app')

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .settings import settings

logging.basicConfig(
    level=settings.LOG_LEVEL,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Psychometry Service",
    description="MMPI-2 and IAT testing service",
    version="3.4",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": settings.SERVICE_NAME}

@app.get("/ready")
async def readiness_check():
    return {"status": "ready"}

@app.get("/")
async def root():
    return {"service": settings.SERVICE_NAME, "version": "3.4", "status": "operational"}

logger.info(f"🚀 Psychometry Service started on port {settings.API_PORT}")