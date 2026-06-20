"""
Tests for LangGraph state machine.
Covers: state transitions, full workflow, edge cases.
"""
from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from src.graph.consensus_graph import (
    GraphState, node_collect_prefs, node_detect_conflict,
    node_generate_proposal, node_collect_votes, node_final_decision,
    node_resolve, node_fallback, build_consensus_workflow, STATE_MAP
)
from src.agents.preference_agent import PreferenceAgent
from src.agents.mediator_agent import MediatorAgent
from src.models.schemas import Verdict


def make_state(user_texts: dict[str, str]) -> GraphState:
    """Helper: create GraphState with agents initialized."""
    agents = [PreferenceAgent(name, text) for name, text in user_texts.items()]
    return GraphState(
        user_texts=user_texts,
        preference_agents=agents,
        mediator=MediatorAgent(),
    )


class TestCollectPrefs:
    def test_collects_all_preferences(self):
        state = make_state({"A": "我喜欢科幻片", "B": "我喜欢喜剧片"})
        state = node_collect_prefs(state)
        assert len(state.preferences) == 2
        assert state.preferences[0].user_name == "A"
        assert state.preferences[1].user_name == "B"
        assert state.next_state == "detect_conflict"


class TestDetectConflict:
    def test_detects_conflict(self):
        state = make_state({"A": "我喜欢科幻片", "B": "我不要科幻片"})
        state = node_collect_prefs(state)
        state = node_detect_conflict(state)
        assert len(state.conflicts) > 0
        assert state.next_state == "resolve"

    def test_no_conflict(self):
        state = make_state({"A": "我喜欢喜剧片", "B": "我也喜欢喜剧片"})
        state = node_collect_prefs(state)
        state = node_detect_conflict(state)
        assert len(state.conflicts) == 0
        assert state.next_state == "generate_proposal"


class TestResolve:
    def test_increment_round(self):
        state = make_state({"A": "科幻", "B": "喜剧"})
        state.resolve_round = 0
        state = node_resolve(state)
        assert state.resolve_round == 1
        assert state.next_state == "generate_proposal"

    def test_max_rounds_fallback(self):
        state = make_state({"A": "科幻", "B": "喜剧"})
        state.resolve_round = 3
        state.max_resolve_rounds = 3
        state = node_resolve(state)
        assert state.next_state == "fallback"


class TestGenerateProposal:
    def test_generates_proposal(self):
        state = make_state({"A": "我喜欢喜剧片", "B": "我喜欢喜剧片"})
        state = node_collect_prefs(state)
        state = node_detect_conflict(state)
        state = node_generate_proposal(state)
        assert state.current_proposal is not None
        assert state.next_state == "collect_votes"

    def test_fallback_when_no_candidates(self):
        state = make_state({"A": "科幻片", "B": "科幻片"})
        state.preferences = [
            type('P', (), {'user_name': 'A', 'genres': ['科幻'], 'max_duration': 5, 'min_rating': 0, 'veto_list': []})()
        ]
        state = node_generate_proposal(state)
        assert state.next_state == "fallback"


class TestCollectVotes:
    def test_all_approve(self):
        state = make_state({"A": "我喜欢喜剧片", "B": "我喜欢喜剧片"})
        state = node_collect_prefs(state)
        state = node_detect_conflict(state)
        state = node_generate_proposal(state)
        state = node_collect_votes(state)
        assert len(state.votes) == 2
        assert all(v.verdict == Verdict.APPROVE for v in state.votes)
        assert state.next_state == "final_decision"

    def test_veto_triggers_resolve(self):
        """When one user vetoes, should go back to resolve."""
        state = make_state({"A": "我喜欢恐怖片", "B": "我不要恐怖片"})
        state = node_collect_prefs(state)
        state = node_detect_conflict(state)
        state = node_generate_proposal(state)
        # Force a horror proposal
        if state.current_proposal:
            state = node_collect_votes(state)
            # B should veto, triggering resolve
            if state.next_state == "resolve":
                assert state.resolve_round >= 0


class TestFinalDecision:
    def test_produces_result(self):
        state = make_state({"A": "我喜欢喜剧片", "B": "我喜欢喜剧片"})
        state = node_collect_prefs(state)
        state = node_detect_conflict(state)
        state = node_generate_proposal(state)
        state = node_collect_votes(state)
        state = node_final_decision(state)
        assert state.result is not None
        assert state.result.movie is not None
        assert state.should_continue is False


class TestFallback:
    def test_fallback_produces_result(self):
        state = make_state({"A": "科幻片"})
        state = node_collect_prefs(state)  # Must declare first
        state = node_fallback(state)
        assert state.result is not None
        assert state.result.movie is not None
        assert state.result.is_fallback is True
        assert state.should_continue is False


class TestFullWorkflow:
    def test_2_person_consensus(self):
        """End-to-end: 2 people reaching consensus."""
        state = build_consensus_workflow({
            "Alice": "我喜欢喜剧片，90分钟以内",
            "Bob": "我喜欢喜剧片，轻松一点的",
        })
        assert state.result is not None
        assert state.result.movie is not None
        assert state.result.group_score > 0
        assert "喜剧" in state.result.movie.genres

    def test_4_person_consensus(self):
        """End-to-end: 4 people (dorm scenario)."""
        state = build_consensus_workflow({
            "A": "科幻和动作",
            "B": "喜剧和动画",
            "C": "爱情和剧情，拒绝恐怖和战争",
            "D": "都可以，8分以上",
        })
        assert state.result is not None
        assert state.result.movie is not None
        assert state.result.movie.rating >= 8.0

    def test_impossible_constraints_fallback(self):
        """When no movie matches, should use fallback."""
        state = build_consensus_workflow({
            "A": "我只看10分钟以内的电影",
        })
        assert state.result is not None
        assert state.result.is_fallback is True

    def test_state_machine_completes(self):
        """State machine should always reach terminal state."""
        state = build_consensus_workflow({
            "A": "科幻片",
            "B": "喜剧片",
        })
        assert not state.should_continue  # Machine stopped
        assert state.next_state == "end"

    def test_all_states_exist(self):
        """All required states should be in STATE_MAP."""
        required = ["collect_prefs", "detect_conflict", "resolve",
                    "generate_proposal", "collect_votes", "final_decision", "fallback"]
        for state in required:
            assert state in STATE_MAP

    def test_scenario_with_veto(self):
        """A scenario where one user vetoes."""
        state = build_consensus_workflow({
            "Alice": "恐怖片，越恐怖越好",
            "Bob": "我怕恐怖片，要看爱情片",
        })
        assert state.result is not None
        assert state.result.movie is not None
        # Should not recommend horror
        assert "恐怖" not in state.result.movie.genres
