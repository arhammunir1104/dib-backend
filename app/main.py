# app/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import traceback
from app.core.config import settings
from app.logging.setup import logger
# from app.api.routes import health, processing, rcm
from app.db.database import engine
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
# from app.api.routes import rcm

import app.api.routes.health as health
import app.api.routes.processing as processing
import app.api.routes.rcm as rcm
from app.api.routes import rcm_completion


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting DIB Circular AI backend")
    yield
    # Shutdown
    await engine.dispose()
    logger.info("Shutting down")

app = FastAPI(
    title=settings.APP_NAME,
    debug=settings.DEBUG,
    lifespan=lifespan,
)

# Global exception handler – must be after app creation
# @app.exception_handler(Exception)
# async def global_exception_handler(request: Request, exc: Exception):
#     logger.error(f"Unhandled exception: {exc}\n{traceback.format_exc()}")
#     return JSONResponse(
#         status_code=500,
#         content={"detail": "Internal server error. Please contact support."},
#     )
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],   # both Vite & CRA
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # Extract a simplified error message
    errors = exc.errors()
    if errors:
        # Take the first error's message
        detail = errors[0].get("msg", "Validation error")
    else:
        detail = "Validation error"
    logger.warning(f"Validation error: {exc}")
    return JSONResponse(
        status_code=422,
        content={"detail": detail}
)

# Include routers
app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(processing.router, prefix="/api", tags=["processing"])
app.include_router(rcm.router)
app.include_router(rcm_completion.router)
    