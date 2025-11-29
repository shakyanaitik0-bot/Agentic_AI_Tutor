"""
FastAPI application for Agentic AI Tutor.

Main entry point for the REST API server.
Coordinates multi-agent system for adaptive learning.
"""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from app.core.config import settings
from app.api import api_router

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.get("logging.level", "INFO")),
    format=settings.get("logging.format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s")
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    logger.info("Starting Agentic AI Tutor API...")
    logger.info(f"Configuration loaded from config.yaml")
    logger.info(f"LLM Provider: {settings.get('llm.provider')}")
    logger.info(f"Embedding Provider: {settings.get('embeddings.provider')}")

    yield

    # Shutdown
    logger.info("Shutting down Agentic AI Tutor API...")


# Initialize FastAPI app
app = FastAPI(
    title=settings.get("api.title", "Agentic AI Tutor API"),
    description=settings.get("api.description", "Adaptive learning platform with multi-agent AI tutoring"),
    version=settings.get("api.version", "0.1.0"),
    lifespan=lifespan
)


# CORS Configuration
cors_config = settings.get("api.cors", {})
if cors_config.get("enabled", True):
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_config.get("origins", ["*"]),
        allow_credentials=cors_config.get("allow_credentials", True),
        allow_methods=cors_config.get("methods", ["*"]),
        allow_headers=["*"],
    )
    logger.info("CORS enabled")


# Global exception handlers
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors with detailed messages"""
    logger.warning(f"Validation error on {request.url}: {exc}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "ValidationError",
            "message": "Request validation failed",
            "details": exc.errors()
        }
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle unexpected errors"""
    logger.error(f"Unexpected error on {request.url}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "InternalServerError",
            "message": "An unexpected error occurred",
            "details": str(exc) if settings.get("debug", False) else None
        }
    )


# Health check endpoint
@app.get("/health", tags=["Health"])
async def health_check():
    """
    Health check endpoint for monitoring.

    Returns basic system status.
    """
    return {
        "status": "healthy",
        "service": "agentic-ai-tutor",
        "version": settings.get("api.version", "0.1.0"),
        "llm_provider": settings.get("llm.provider"),
        "embedding_provider": settings.get("embeddings.provider")
    }


# Root endpoint
@app.get("/", tags=["Root"])
async def root():
    """
    Root endpoint with API information.
    """
    return {
        "message": "Agentic AI Tutor API",
        "version": settings.get("api.version", "0.1.0"),
        "docs": "/docs",
        "health": "/health"
    }


# Include API router
app.include_router(api_router, prefix=settings.get("api.prefix", "/api"))


if __name__ == "__main__":
    import uvicorn

    # Run with uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # Auto-reload on code changes
        log_level=settings.get("logging.level", "info").lower()
    )
