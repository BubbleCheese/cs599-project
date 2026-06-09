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

import sys
from pathlib import Path

# Get project root and add to path first
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv(project_root / ".env")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field
from typing import Dict, List, Optional
import os

# Check frontend directories
frontend_dist = project_root / "frontend" / "dist"
web_dir = project_root / "web"

app = FastAPI(
    title="Social Consensus Agent API",
    description="Multi-agent group movie recommendation system",
    version="1.0.0",
)

# CORS - allow frontend to call API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ===== Frontend serving - MUST be first =====
@app.get("/")
async def serve_frontend():
    """Serve the frontend index page."""
    if frontend_dist.exists() and (frontend_dist / "index.html").exists():
        index_path = frontend_dist / "index.html"
    elif web_dir.exists() and (web_dir / "index.html").exists():
        index_path = web_dir / "index.html"
    else:
        return HTMLResponse(content="<h1>Frontend not found</h1>", status_code=404)
    
    return FileResponse(str(index_path))


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
    from main import SCENARIOS
    return [
        {"id": k, "name": v["name"], "users": v["users"]}
        for k, v in sorted(SCENARIOS.items())
    ]


@app.post("/api/negotiate")
def negotiate(req: NegotiateRequest):
    """
    Run consensus workflow.
    
    Example request:
    {
        "users": [
            {"name": "Alice", "preference": "我喜欢科幻片"},
            {"name": "Bob", "preference": "我喜欢喜剧片"}
        ]
    }
    """
    from src.graph.consensus_graph import build_consensus_workflow
    from src.llm.mock import create_llm
    from src.memory.vector_store import create_hierarchical_store

    user_texts = {u.name: u.preference for u in req.users}

    # Print header like main.py
    print("\n" + "=" * 60)
    print("  Social Consensus Agent - Frontend Request")
    print(f"  群体人数: {len(user_texts)}人 | LLM: {'DeepSeek' if req.use_llm else 'Mock'} | Memory: Hierarchical")
    print("=" * 60)
    for name, pref in user_texts.items():
        print(f"  {name}: \"{pref}\"")

    llm = create_llm() if req.use_llm else None
    # Use hierarchical storage: ChromaDB for persistence, Memory for temporary
    vector_store = create_hierarchical_store() if req.use_chroma else None

    state = build_consensus_workflow(user_texts, llm=llm, vector_store=vector_store)

    # Print log
    print("\n【协商日志】")
    for log in state.log:
        print(f"  > {log}")

    # Print result
    if state.result and state.result.movie:
        print(f"\n【最终推荐】《{state.result.movie.title}》")
        print(f"  群体满意度: {state.result.group_score}/10")
        print(f"  协商轮次: {state.result.rounds_taken}")
        if state.result.dissenters:
            print(f"  异议者: {', '.join(state.result.dissenters)}")
        print("=" * 60)

    if state.result is None:
        return {"error": "Consensus failed", "log": state.log}

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


@app.get("/api/movies")
def list_movies(genre: Optional[str] = None, limit: int = 20):
    """List available movies with optional genre filter."""
    from src.data.movies import search_movies
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
