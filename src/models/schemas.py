"""
Social Consensus Agent - Data Models
Pydantic schemas for Agent communication and state management.
"""
from __future__ import annotations

from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class Verdict(str, Enum):
    """Vote verdict options."""
    APPROVE = "approve"
    VETO = "veto"
    ABSTAIN = "abstain"


class PreferenceVector(BaseModel):
    """Structured user preference declaration."""
    user_name: str
    genres: List[str] = Field(default_factory=list, description="Preferred genres")
    max_duration: int = Field(default=180, description="Max acceptable duration in minutes")
    min_rating: float = Field(default=0.0, description="Minimum rating threshold")
    veto_list: List[str] = Field(default_factory=list, description="Hard constraints (e.g., ['horror'])")
    soft_prefs: str = Field(default="", description="Natural language soft preferences")


class Movie(BaseModel):
    """Movie metadata."""
    movie_id: str
    title: str
    genres: List[str]
    duration: int  # minutes
    rating: float  # 0-10
    year: int = 2020
    description: str = ""


class Proposal(BaseModel):
    """Movie proposal sent by Mediator to PreferenceAgents."""
    movie: Movie
    compromise_rules_applied: List[str] = Field(default_factory=list)
    reason: str = ""
    round_num: int = 1


class VoteResult(BaseModel):
    """Vote from a PreferenceAgent on a proposal."""
    user_name: str
    score: int = Field(ge=1, le=10, description="Satisfaction score 1-10")
    verdict: Verdict = Verdict.ABSTAIN
    reason: str = ""


class ConsensusResult(BaseModel):
    """Final consensus output."""
    movie: Optional[Movie] = None
    group_score: float = 0.0
    votes: List[VoteResult] = Field(default_factory=list)
    negotiation_log: List[str] = Field(default_factory=list)
    rounds_taken: int = 0
    dissenters: List[str] = Field(default_factory=list)
    is_fallback: bool = False


class AgentState(BaseModel):
    """LangGraph state for the consensus workflow."""
    # Inputs
    user_inputs: Dict[str, str] = Field(default_factory=dict, description="raw user preference texts")
    
    # Collected preferences
    preferences: List[PreferenceVector] = Field(default_factory=list)
    
    # Current proposal
    current_proposal: Optional[Proposal] = None
    proposal_candidates: List[Movie] = Field(default_factory=list)
    
    # Votes
    votes: List[VoteResult] = Field(default_factory=list)
    
    # Conflict resolution
    conflicts_detected: List[str] = Field(default_factory=list)
    resolve_round: int = 0
    max_resolve_rounds: int = 3
    
    # Final result
    result: Optional[ConsensusResult] = None
    
    # Logging
    log: List[str] = Field(default_factory=list)
    
    def add_log(self, message: str) -> None:
        self.log.append(message)
        print(f"  [{len(self.log)}] {message}")

    class Config:
        arbitrary_types_allowed = True
