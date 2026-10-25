"""Run with: python -m uvicorn backend.api.main:app --reload."""

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from backend.api.player_routes import router as player_router
from backend.api.workspace import router as workspace_router
from backend.api.routes import router
from backend.api.xt_routes import router as xt_router

app = FastAPI(title="Football Intelligence Lab API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000"],
                   allow_methods=["GET"], allow_headers=["Accept", "Content-Type"],
                   allow_credentials=False)
app.include_router(router, prefix="/api/v1")
app.include_router(xt_router, prefix="/api/v1")
app.include_router(workspace_router, prefix="/api/v1")
app.include_router(player_router, prefix="/api/v1")


@app.exception_handler(ValidationError)
@app.exception_handler(ValueError)
@app.exception_handler(KeyError)
@app.exception_handler(AttributeError)
def invalid_provider_data(request: Request, exc: Exception):
    """Report invalid provider schemas without exposing internals to clients."""
    logging.getLogger(__name__).warning("Invalid provider data for %s: %s", request.url.path, type(exc).__name__)
    return JSONResponse(status_code=502, content={"detail": "Invalid data returned by provider"})
