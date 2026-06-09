"""
LangGraph State Machine - Consensus Workflow (Final Version).
Supports: N users, LLM-enhanced agents, Chroma vector store, MCP tools.
States: collect_prefs -> detect_conflict -> [resolve] -> generate_proposal
        -> collect_votes -> final_decision
"""
from __future__ import annotations

from dataclasses import dataclass, field

from src.models.schemas import (
    PreferenceVector, Proposal, VoteResult, ConsensusResult, Verdict
)
from src.agents.preference_agent import PreferenceAgent
from src.agents.mediator_agent import MediatorAgent
from src.llm.base import BaseLLM
from src.memory.vector_store import BaseVectorStore


@dataclass
class GraphState:
    """State object passed between graph nodes."""
    user_texts: dict[str, str] = field(default_factory=dict)
    preference_agents: list[PreferenceAgent] = field(default_factory=list)
    mediator: MediatorAgent | None = None
    preferences: list[PreferenceVector] = field(default_factory=list)
    current_proposal: Proposal | None = None
    votes: list[VoteResult] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    resolve_round: int = 0
    max_resolve_rounds: int = 3
    rejected_movie_ids: list[str] = field(default_factory=list)
    result: ConsensusResult | None = None
    should_continue: bool = True
    next_state: str = "collect_prefs"
    log: list[str] = field(default_factory=list)

    def add_log(self, msg: str) -> None:
        self.log.append(msg)


def node_collect_prefs(state: GraphState) -> GraphState:
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
        state.add_log("  无冲突，直接进入提案生成")
        state.next_state = "generate_proposal"
    return state


def node_resolve(state: GraphState) -> GraphState:
    state.add_log("=== STATE: resolve ===")
    state.resolve_round += 1
    state.add_log(f"  冲突解决轮次: {state.resolve_round}/{state.max_resolve_rounds}")
    if state.resolve_round > state.max_resolve_rounds:
        state.add_log("  超过最大轮次，进入 fallback")
        state.next_state = "fallback"
        return state
    state.add_log("  妥协策略：R1类型交叉 + R2时长约束 + R3历史加权")
    state.next_state = "generate_proposal"
    return state


def node_generate_proposal(state: GraphState) -> GraphState:
    state.add_log("=== STATE: generate_proposal ===")
    if state.mediator is None:
        raise RuntimeError("MediatorAgent not initialized")
    proposal = state.mediator.generate_proposal(
        preferences=state.preferences,
        round_num=state.resolve_round + 1,
        exclude_movie_ids=state.rejected_movie_ids
    )
    if proposal is None:
        state.add_log("  无候选影片，进入 fallback")
        state.next_state = "fallback"
        return state
    state.current_proposal = proposal
    movie = proposal.movie
    state.add_log(f"  提案 #{proposal.round_num}: 《{movie.title}》")
    state.add_log(f"    类型{movie.genres} 时长{movie.duration}min 评分{movie.rating}")
    state.add_log(f"    规则: {', '.join(proposal.compromise_rules_applied)}")
    state.next_state = "collect_votes"
    return state


def node_collect_votes(state: GraphState) -> GraphState:
    state.add_log("=== STATE: collect_votes ===")
    if state.current_proposal is None:
        raise RuntimeError("No proposal to vote on")
    state.votes = []
    any_veto = False
    for agent in state.preference_agents:
        vote = agent.vote(state.current_proposal)
        state.votes.append(vote)
        marker = "VETO" if vote.verdict == Verdict.VETO else f"{vote.score}分"
        state.add_log(f"  {vote.user_name}: {marker} - {vote.reason}")
        if vote.verdict == Verdict.VETO:
            any_veto = True
    if any_veto and state.resolve_round < state.max_resolve_rounds:
        state.add_log("  存在否决，返回 resolve")
        if state.current_proposal:
            state.rejected_movie_ids.append(state.current_proposal.movie.movie_id)
        state.next_state = "resolve"
    else:
        state.add_log("  投票完成，进入裁决")
        state.next_state = "final_decision"
    return state


def node_final_decision(state: GraphState) -> GraphState:
    state.add_log("=== STATE: final_decision ===")
    if state.mediator is None or state.current_proposal is None:
        raise RuntimeError("Missing mediator or proposal")
    result = state.mediator.finalize(state.current_proposal, state.votes)
    state.result = result
    movie = result.movie
    state.add_log(f"\n{'='*50}")
    state.add_log(f"最终推荐: 《{movie.title}》")
    state.add_log(f"类型: {movie.genres} | 时长: {movie.duration}min | 评分: {movie.rating}")
    state.add_log(f"群体满意度: {result.group_score:.1f}/10 | 轮次: {result.rounds_taken}")
    if result.dissenters:
        state.add_log(f"异议者: {', '.join(result.dissenters)}")
    if result.is_fallback:
        state.add_log("[安全牌推荐]")
    state.add_log(f"{'='*50}")
    state.should_continue = False
    state.next_state = "end"
    return state


def node_fallback(state: GraphState) -> GraphState:
    state.add_log("=== STATE: fallback ===")
    if state.mediator is None:
        raise RuntimeError("MediatorAgent not initialized")
    proposal = state.mediator.apply_safe_fallback()
    state.current_proposal = proposal
    votes = []
    for agent in state.preference_agents:
        vote = agent.vote(proposal)
        votes.append(vote)
        state.add_log(f"  {vote.user_name}: {vote.score}分 - {vote.reason}")
    result = state.mediator.finalize(proposal, votes)
    result.is_fallback = True
    state.result = result
    movie = result.movie
    state.add_log(f"\n{'='*50}")
    state.add_log(f"最终推荐 [安全牌]: 《{movie.title}》")
    state.add_log(f"群体满意度: {result.group_score:.1f}/10")
    state.add_log(f"{'='*50}")
    state.should_continue = False
    state.next_state = "end"
    return state


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
    user_texts: dict[str, str],
    llm: BaseLLM | None = None,
    vector_store: BaseVectorStore | None = None,
) -> GraphState:
    """
    Build and run the consensus workflow.

    Args:
        user_texts: {user_name: preference_text}
        llm: Optional LLM provider (DeepSeek or Mock)
        vector_store: Optional vector store (Chroma or Memory)

    Returns:
        Final GraphState with consensus result.
    """
    n_users = len(user_texts)
    preference_agents = [
        PreferenceAgent(name, text, llm=llm)
        for name, text in user_texts.items()
    ]
    mediator = MediatorAgent(vector_store=vector_store)

    state = GraphState(
        user_texts=user_texts,
        preference_agents=preference_agents,
        mediator=mediator
    )

    # Print header
    llm_status = llm.config.provider if llm else "none"
    store_status = vector_store.get_stats().get("provider", "none") if vector_store else "none"
    print(f"\n{'='*60}")
    print(f"  Social Consensus Agent - Final Demo")
    print(f"  群体人数: {n_users}人 | LLM: {llm_status} | Memory: {store_status}")
    print(f"{'='*60}")
    for name, text in user_texts.items():
        print(f"  {name}: \"{text}\"")
    print()

    # Run state machine
    max_steps = 20
    step = 0
    while state.should_continue and step < max_steps:
        step += 1
        current = state.next_state
        if current not in STATE_MAP or current == "end":
            break
        node_fn = STATE_MAP[current]
        state = node_fn(state)

    return state
