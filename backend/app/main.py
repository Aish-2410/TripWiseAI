"""TripWise AI - FastAPI application entry point."""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .ai import llm
from .ai.engine import get_engine
from .api.routes import router
from .config import CORS_ORIGINS, ROOT

log = logging.getLogger("tripwise")
app = FastAPI(title="TripWise AI", version="1.0.0", description="Intelligent travel-planning concierge: search, knowledge representation, rules and budget optimisation.")
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_methods=["*"], allow_headers=["*"])
app.include_router(router)


@app.on_event("startup")
def _warm() -> None:
    e = get_engine()  # load dataset + build knowledge base once
    log.info("TripWise ready: %d destinations, %d attractions, %d KB facts, %d data issues", len(e.ds.destinations), len(e.ds.attractions), len(e.kb.facts), len(e.ds.issues))
    st = llm.status()   # never includes the key
    if st["enabled"]:
        log.info("Gemini understanding enabled (model %s); results still come from the dataset and the planner. Rule-based fallback is always available.", st["model"])
    else:
        log.info("Gemini understanding disabled (%s). Using the rule-based parser.", "GEMINI_API_KEY not set" if not st["configured"] else "GEMINI_ENABLED=false")


@app.exception_handler(Exception)
async def _unhandled(request: Request, exc: Exception):
    log.exception("unhandled error on %s", request.url.path)
    return JSONResponse(status_code=500, content=dict(detail="Something went wrong on our side. Please try again."))


dist = ROOT / "frontend" / "dist"
if dist.exists():  # optional single-process demo: serve the built SPA
    app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        f = dist / full_path
        return FileResponse(f if f.is_file() else dist / "index.html")
