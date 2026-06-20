"""
FastAPI Backend - REST API for Social Consensus Agent.

Endpoints:
    POST /api/negotiate     - Run consensus workflow
    GET  /api/movies        - List/search movies
    GET  /api/scenarios     - Get demo scenarios
    GET  /api/health        - Health check

Run:
    uvicorn src.api.server:app --reload --port 8000
"""
from __future__ import annotations

import logging
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

# Get project root and add to path first
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv(project_root / ".env")

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, Field, ValidationError
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("social_consensus_agent")

# Check frontend directories
frontend_dist = project_root / "frontend" / "dist"
web_dir = project_root / "web"

app = FastAPI(
    title="Social Consensus Agent API",
    description="Multi-agent group movie recommendation system",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# CORS - allow frontend to call API with security constraints
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
    max_age=3600,  # Cache preflight requests for 1 hour
)


# ===== Error Handlers =====

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors with detailed logging."""
    logger.error(f"Validation error in {request.method} {request.url.path}: {exc.errors()}")
    return {
        "error": "validation_error",
        "message": "请求参数验证失败",
        "details": exc.errors()
    }, status.HTTP_422_UNPROCESSABLE_ENTITY


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions with logging."""
    logger.exception(f"Unexpected error in {request.method} {request.url.path}: {str(exc)}")
    return {
        "error": "internal_server_error",
        "message": "服务器内部错误，请稍后重试"
    }, status.HTTP_500_INTERNAL_SERVER_ERROR


# ===== Middleware =====

@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all requests with timing and error tracking."""
    start_time = time.time()
    
    # Log request
    logger.info(f"{request.method} {request.url.path} - Started")
    
    try:
        # Process request
        response = await call_next(request)
        
        # Calculate duration
        duration = time.time() - start_time
        
        # Log response
        log_level = logging.WARNING if response.status_code >= 400 else logging.INFO
        logger.log(log_level, f"{request.method} {request.url.path} - {response.status_code} - {duration:.3f}s")
        
        return response
        
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"{request.method} {request.url.path} - Error after {duration:.3f}s: {str(e)}")
        raise


# ===== Frontend serving - MUST be first =====
@app.get("/")
async def serve_frontend():
    """Serve the frontend index page."""
    try:
        if frontend_dist.exists() and (frontend_dist / "index.html").exists():
            index_path = frontend_dist / "index.html"
        elif web_dir.exists() and (web_dir / "index.html").exists():
            index_path = web_dir / "index.html"
        else:
            logger.warning("Frontend not found")
            return HTMLResponse(content="<h1>Frontend not found</h1>", status_code=404)
        
        return FileResponse(str(index_path))
    except Exception as e:
        logger.exception(f"Error serving frontend: {e}")
        raise HTTPException(status_code=500, detail="Failed to serve frontend")


# ===== Pydantic Models =====

class UserPreference(BaseModel):
    name: str = Field(..., description="User name")
    preference: str = Field(..., description="Natural language preference text")


class NegotiateRequest(BaseModel):
    users: List[UserPreference] = Field(..., description="List of user preferences")
    use_llm: bool = Field(default=False, description="Use LLM if available")
    use_chroma: bool = Field(default=False, description="Use Chroma vector store")


class MovieResponse(BaseModel):
    movie_id: str
    title: str
    genres: List[str]
    duration: int
    rating: float
    year: int
    description: str = ""


class VoteResponse(BaseModel):
    user_name: str
    score: int
    verdict: str
    reason: str


class ConsensusResponse(BaseModel):
    movie: Optional[MovieResponse] = None
    group_score: float
    votes: List[VoteResponse]
    negotiation_log: List[str]
    rounds_taken: int
    dissenters: List[str]
    is_fallback: bool


class ScenarioResponse(BaseModel):
    id: int
    name: str
    users: Dict[str, str]


# ===== API Endpoints =====

@app.get("/api/health")
def health():
    """Health check endpoint."""
    return {"status": "ok", "version": "1.0.0"}


@app.get("/api/scenarios")
def get_scenarios():
    """Get all demo scenarios."""
    try:
        from main import SCENARIOS
        return [
            {"id": k, "name": v["name"], "users": v["users"]}
            for k, v in sorted(SCENARIOS.items())
        ]
    except Exception as e:
        logger.exception(f"Failed to load scenarios: {e}")
        raise HTTPException(status_code=500, detail="Failed to load scenarios")


@app.post("/api/negotiate")
async def negotiate(req: NegotiateRequest):
    """
    Run consensus workflow with comprehensive error handling.
    
    Example request:
    {
        "users": [
            {"name": "Alice", "preference": "我喜欢科幻片"},
            {"name": "Bob", "preference": "我喜欢喜剧片"}
        ]
    }
    """
    import traceback
    from src.graph.consensus_graph import build_consensus_workflow
    from src.llm.mock import create_llm
    from src.memory.vector_store import create_hierarchical_store

    try:
        # Validate input
        if not req.users or len(req.users) == 0:
            logger.warning("Empty users list in negotiate request")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="至少需要一个用户"
            )
        
        if len(req.users) > 10:
            logger.warning(f"Too many users: {len(req.users)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="最多支持 10 个用户"
            )

        user_texts = {u.name: u.preference for u in req.users}

        # Log request with logger instead of print
        logger.info("\n" + "=" * 60)
        logger.info("  Social Consensus Agent - Frontend Request")
        logger.info(f"  群体人数：{len(user_texts)}人 | LLM: {'DeepSeek' if req.use_llm else 'Mock'} | Memory: Hierarchical")
        logger.info("=" * 60)
        for name, pref in user_texts.items():
            logger.info(f"  {name}: \"{pref}\"")

        # Create LLM and vector store with error handling
        try:
            llm = create_llm() if req.use_llm else None
        except Exception as e:
            logger.warning(f"LLM creation failed: {e}, falling back to Mock")
            llm = None
        
        try:
            vector_store = create_hierarchical_store() if req.use_chroma else None
        except Exception as e:
            logger.warning(f"Vector store creation failed: {e}, using None")
            vector_store = None

        # Run consensus workflow
        state = build_consensus_workflow(user_texts, llm=llm, vector_store=vector_store)

        # Log results
        logger.info("\n【协商日志】")
        for log in state.log:
            logger.info(f"  > {log}")

        if state.result and state.result.movie:
            logger.info(f"\n【最终推荐】《{state.result.movie.title}》")
            logger.info(f"  群体满意度：{state.result.group_score}/10")
            logger.info(f"  协商轮次：{state.result.rounds_taken}")
            if state.result.dissenters:
                logger.info(f"  异议者：{', '.join(state.result.dissenters)}")
            logger.info("=" * 60)

        if state.result is None:
            logger.warning("Consensus failed - no result")
            return {
                "error": "consensus_failed",
                "message": "未能达成共识，请尝试调整偏好",
                "log": state.log
            }

        r = state.result
        return ConsensusResponse(
            movie=MovieResponse(
                movie_id=r.movie.movie_id,
                title=r.movie.title,
                genres=r.movie.genres,
                duration=r.movie.duration,
                rating=r.movie.rating,
                year=r.movie.year,
                description=r.movie.description,
            ) if r.movie else None,
            group_score=r.group_score,
            votes=[
                VoteResponse(
                    user_name=v.user_name,
                    score=v.score,
                    verdict=v.verdict.value,
                    reason=v.reason,
                )
                for v in r.votes
            ],
            negotiation_log=state.log,
            rounds_taken=r.rounds_taken,
            dissenters=r.dissenters,
            is_fallback=r.is_fallback,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Negotiation failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"协商失败：{str(e)}"
        )


@app.get("/api/movies")
def list_movies(genre: Optional[str] = None, limit: int = 20):
    """List available movies with optional genre filter."""
    try:
        from src.data.movies import search_movies
        
        # Validate limit
        if limit < 1:
            limit = 1
        elif limit > 100:
            limit = 100
            
        results = search_movies(
            genres=[genre] if genre else None,
            limit=limit,
        )
        return [
            MovieResponse(
                movie_id=m.movie_id,
                title=m.title,
                genres=m.genres,
                duration=m.duration,
                rating=m.rating,
                year=m.year,
                description=m.description,
            )
            for m in results
        ]
    except Exception as e:
        logger.exception(f"Failed to list movies: {e}")
        raise HTTPException(status_code=500, detail="Failed to list movies")
