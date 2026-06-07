"""
LangGraph State Machine - Consensus Workflow.
States: collect_prefs -> detect_conflict -> [resolve] -> generate_proposal 
        -> collect_votes -> final_decision
"""
from __future__ import annotations

from typing import List, Literal
from dataclasses import dataclass, field

from src.models.schemas import (
    PreferenceVector, Proposal, VoteResult, ConsensusResult, Verdict
)
from src.agents.preference_agent import PreferenceAgent
from src.agents.mediator_agent import MediatorAgent


# === State Types for LangGraph ===
@dataclass
class GraphState:
    """State object passed between graph nodes."""
    # Input
    user_texts: dict[str, str] = field(default_factory=dict)
    
    # Agents
    preference_agents: list[PreferenceAgent] = field(default_factory=list)
    mediator: MediatorAgent | None = None
    
    # Collected data
    preferences: list[PreferenceVector] = field(default_factory=list)
    current_proposal: Proposal | None = None
    votes: list[VoteResult] = field(default_factory=list)
    
    # Conflict resolution tracking
    conflicts: list[str] = field(default_factory=list)
    resolve_round: int = 0
    max_resolve_rounds: int = 3
    rejected_movie_ids: list[str] = field(default_factory=list)
    
    # Output
    result: ConsensusResult | None = None
    
    # Status
    should_continue: bool = True
    next_state: str = "collect_prefs"
    
    # Logging
    log: list[str] = field(default_factory=list)
    
    def add_log(self, msg: str) -> None:
        self.log.append(msg)
        print(f"  [GRAPH] {msg}")


# === Node Functions ===

def node_collect_prefs(state: GraphState) -> GraphState:
    """
    STATE: collect_prefs
    Each PreferenceAgent declares their preferences.
    Transition: -> detect_conflict
    """
    state.add_log("=== STATE: collect_prefs ===")
    
    for agent in state.preference_agents:
        pref = agent.declare(agent.raw_input)
        state.preferences.append(pref)
        state.add_log(
            f"  {pref.user_name}: 偏好={pref.genres}, "
            f"最大时长={pref.max_duration}min, "
            f"最低评分={pref.min_rating}, "
            f"否决={pref.veto_list}"
        )
    
    state.next_state = "detect_conflict"
    return state


def node_detect_conflict(state: GraphState) -> GraphState:
    """
    STATE: detect_conflict
    Mediator analyzes preferences for conflicts.
    Transition: -> resolve (if conflicts) | -> generate_proposal (if no conflicts)
    """
    state.add_log("=== STATE: detect_conflict ===")
    
    if state.mediator is None:
        raise RuntimeError("MediatorAgent not initialized")
    
    state.conflicts = state.mediator.detect_conflicts(state.preferences)
    
    if state.conflicts:
        state.add_log(f"  检测到 {len(state.conflicts)} 个冲突:")
        for c in state.conflicts:
            state.add_log(f"    - {c}")
        state.next_state = "resolve"
    else:
        state.add_log("  无冲突检测到，直接进入提案生成")
        state.next_state = "generate_proposal"
    
    return state


def node_resolve(state: GraphState) -> GraphState:
    """
    STATE: resolve
    Apply compromise rules to resolve conflicts.
    Transition: -> generate_proposal (resolved) | -> fallback (max rounds)
    """
    state.add_log("=== STATE: resolve ===")
    state.resolve_round += 1
    state.add_log(f"  冲突解决轮次: {state.resolve_round}/{state.max_resolve_rounds}")
    
    if state.resolve_round > state.max_resolve_rounds:
        state.add_log("  超过最大解决轮次，进入 fallback")
        state.next_state = "fallback"
        return state
    
    # Log the resolution strategy
    state.add_log("  妥协策略：")
    state.add_log("    - R1: 过滤冲突类型，保留安全类型交集")
    state.add_log("    - R2: 使用时长中位数作为上限")
    state.add_log("    - R3: 使用最高评分阈值")
    
    state.next_state = "generate_proposal"
    return state


def node_generate_proposal(state: GraphState) -> GraphState:
    """
    STATE: generate_proposal
    Mediator generates a movie proposal based on (resolved) preferences.
    Transition: -> collect_votes
    """
    state.add_log("=== STATE: generate_proposal ===")
    
    if state.mediator is None:
        raise RuntimeError("MediatorAgent not initialized")
    
    proposal = state.mediator.generate_proposal(
        preferences=state.preferences,
        round_num=state.resolve_round + 1,
        exclude_movie_ids=state.rejected_movie_ids
    )
    
    if proposal is None:
        state.add_log("  无候选影片可推荐，进入 fallback")
        state.next_state = "fallback"
        return state
    
    state.current_proposal = proposal
    movie = proposal.movie
    state.add_log(f"  生成提案 #{proposal.round_num}: {movie.title}")
    state.add_log(f"    类型: {movie.genres}, 时长: {movie.duration}min, 评分: {movie.rating}")
    state.add_log(f"    规则: {', '.join(proposal.compromise_rules_applied)}")
    state.add_log(f"    理由: {proposal.reason}")
    
    state.next_state = "collect_votes"
    return state


def node_collect_votes(state: GraphState) -> GraphState:
    """
    STATE: collect_votes
    Each PreferenceAgent votes on the current proposal.
    Transition: -> final_decision (no veto) | -> resolve (veto exists, retry)
    """
    state.add_log("=== STATE: collect_votes ===")
    
    if state.current_proposal is None:
        raise RuntimeError("No proposal to vote on")
    
    state.votes = []
    any_veto = False
    
    for agent in state.preference_agents:
        vote = agent.vote(state.current_proposal)
        state.votes.append(vote)
        state.add_log(
            f"  {vote.user_name}: {vote.verdict.value} "
            f"(评分 {vote.score}/10) - {vote.reason}"
        )
        if vote.verdict == Verdict.VETO:
            any_veto = True
    
    if any_veto and state.resolve_round < state.max_resolve_rounds:
        state.add_log("  存在否决票，返回冲突解决")
        # Add current movie to rejected list so we don't propose it again
        if state.current_proposal:
            state.rejected_movie_ids.append(state.current_proposal.movie.movie_id)
        state.next_state = "resolve"
    else:
        state.add_log("  投票完成，进入最终裁决")
        state.next_state = "final_decision"
    
    return state


def node_final_decision(state: GraphState) -> GraphState:
    """
    STATE: final_decision
    Mediator aggregates votes and produces final consensus.
    This is a terminal state.
    """
    state.add_log("=== STATE: final_decision ===")
    
    if state.mediator is None or state.current_proposal is None:
        raise RuntimeError("Missing mediator or proposal")
    
    result = state.mediator.finalize(state.current_proposal, state.votes)
    state.result = result
    
    movie = result.movie
    state.add_log(f"\n  {'='*50}")
    state.add_log(f"  最终推荐: 《{movie.title}》")
    state.add_log(f"  类型: {movie.genres}")
    state.add_log(f"  时长: {movie.duration}分钟")
    state.add_log(f"  评分: {movie.rating}/10")
    state.add_log(f"  群体满意度: {result.group_score:.1f}/10")
    state.add_log(f"  协商轮次: {result.rounds_taken}")
    if result.dissenters:
        state.add_log(f"  异议者: {', '.join(result.dissenters)}")
    if result.is_fallback:
        state.add_log(f"  [安全牌推荐]")
    state.add_log(f"  {'='*50}\n")
    
    state.should_continue = False
    state.next_state = "end"
    return state


def node_fallback(state: GraphState) -> GraphState:
    """
    STATE: fallback
    All rules failed or max rounds exceeded. Return a safe pick.
    Terminal state.
    """
    state.add_log("=== STATE: fallback ===")
    
    if state.mediator is None:
        raise RuntimeError("MediatorAgent not initialized")
    
    proposal = state.mediator.apply_safe_fallback()
    state.current_proposal = proposal
    
    # Collect votes on the safe pick
    votes = []
    for agent in state.preference_agents:
        vote = agent.vote(proposal)
        votes.append(vote)
        state.add_log(
            f"  {vote.user_name}: {vote.verdict.value} "
            f"(评分 {vote.score}/10) - {vote.reason}"
        )
    
    result = state.mediator.finalize(proposal, votes)
    result.is_fallback = True
    state.result = result
    
    movie = result.movie
    state.add_log(f"\n  {'='*50}")
    state.add_log(f"  最终推荐 [安全牌]: 《{movie.title}》")
    state.add_log(f"  类型: {movie.genres}")
    state.add_log(f"  时长: {movie.duration}分钟")
    state.add_log(f"  评分: {movie.rating}/10")
    state.add_log(f"  群体满意度: {result.group_score:.1f}/10")
    state.add_log(f"  {'='*50}\n")
    
    state.should_continue = False
    state.next_state = "end"
    return state


# === Graph Builder ===

STATE_MAP = {
    "collect_prefs": node_collect_prefs,
    "detect_conflict": node_detect_conflict,
    "resolve": node_resolve,
    "generate_proposal": node_generate_proposal,
    "collect_votes": node_collect_votes,
    "final_decision": node_final_decision,
    "fallback": node_fallback,
}


def build_consensus_workflow(
    user_texts: dict[str, str]
) -> GraphState:
    """
    Build and run the consensus workflow.
    
    Args:
        user_texts: dict mapping user_name -> preference description
                   e.g., {"Alice": "我想看科幻片，不要恐怖", "Bob": "我想看喜剧，不要超过90分钟"}
    
    Returns:
        Final GraphState containing the consensus result.
    """
    # Initialize agents
    preference_agents = [
        PreferenceAgent(name, text)
        for name, text in user_texts.items()
    ]
    mediator = MediatorAgent()
    
    # Initialize state
    state = GraphState(
        user_texts=user_texts,
        preference_agents=preference_agents,
        mediator=mediator
    )
    
    print(f"\n{'='*60}")
    print(f"  Social Consensus Agent - MVP Demo")
    print(f"  群体人数: {len(user_texts)}人")
    print(f"  协商维度: 类型 + 时长")
    print(f"{'='*60}\n")
    
    # Run the state machine
    max_steps = 20
    step = 0
    
    while state.should_continue and step < max_steps:
        step += 1
        current = state.next_state
        
        if current not in STATE_MAP:
            state.add_log(f"Unknown state: {current}, terminating")
            break
        
        if current == "end":
            break
        
        # Execute node
        node_fn = STATE_MAP[current]
        state = node_fn(state)
    
    if step >= max_steps:
        state.add_log("达到最大步数限制，强制终止")
    
    return state
