"""
Tests for PreferenceAgent and MediatorAgent.
Covers: preference parsing, voting, conflict detection, proposal generation.
"""
from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from src.agents.preference_agent import PreferenceAgent
from src.agents.mediator_agent import MediatorAgent
from src.models.schemas import Verdict


class TestPreferenceAgent:
    """Test PreferenceAgent: declare() and vote()"""

    @pytest.fixture
    def agent(self):
        return PreferenceAgent("TestUser", "我喜欢科幻片，不要恐怖片，90分钟以内")

    def test_declare_parses_genres(self, agent):
        pref = agent.declare()
        assert "科幻" in pref.genres
        assert "恐怖" not in pref.genres  # negated genre should not be in preferences

    def test_declare_parses_veto(self, agent):
        pref = agent.declare()
        assert "恐怖" in pref.veto_list

    def test_declare_parses_duration(self, agent):
        pref = agent.declare()
        assert pref.max_duration <= 95  # 90min + buffer

    def test_declare_handles_negation_combined(self):
        """Test '拒绝恐怖和战争' parses both as veto."""
        agent = PreferenceAgent("User", "我喜欢爱情片，拒绝恐怖和战争")
        pref = agent.declare()
        assert "爱情" in pref.genres
        assert "恐怖" in pref.veto_list
        assert "战争" in pref.veto_list
        assert "恐怖" not in pref.genres
        assert "战争" not in pref.genres

    def test_declare_default_genre(self):
        """When no genre specified, default to 剧情."""
        agent = PreferenceAgent("User", "随便都可以")
        pref = agent.declare()
        assert pref.genres == ["剧情"]

    def test_vote_approve(self, agent):
        """Vote should approve a matching movie."""
        from src.models.schemas import Proposal, Movie
        agent.declare()
        proposal = Proposal(
            movie=Movie(movie_id="t01", title="Test Sci-Fi", genres=["科幻"], duration=85, rating=8.5)
        )
        vote = agent.vote(proposal)
        assert vote.verdict == Verdict.APPROVE
        assert vote.score >= 6

    def test_vote_veto_genre(self, agent):
        """Vote should veto a movie with vetoed genre."""
        from src.models.schemas import Proposal, Movie
        agent.declare()
        proposal = Proposal(
            movie=Movie(movie_id="t02", title="Horror Movie", genres=["恐怖"], duration=80, rating=7.0)
        )
        vote = agent.vote(proposal)
        assert vote.verdict == Verdict.VETO
        assert "恐怖" in vote.reason

    def test_vote_veto_duration(self, agent):
        """Vote should veto a movie exceeding duration limit."""
        from src.models.schemas import Proposal, Movie
        agent.declare()
        proposal = Proposal(
            movie=Movie(movie_id="t03", title="Long Movie", genres=["科幻"], duration=200, rating=9.0)
        )
        vote = agent.vote(proposal)
        assert vote.verdict == Verdict.VETO
        assert "时长" in vote.reason

    def test_vote_high_score(self):
        """A perfect match should get high score."""
        agent = PreferenceAgent("User", "我喜欢喜剧片")
        agent.declare()
        from src.models.schemas import Proposal, Movie
        proposal = Proposal(
            movie=Movie(movie_id="t04", title="Great Comedy", genres=["喜剧"], duration=90, rating=9.5)
        )
        vote = agent.vote(proposal)
        assert vote.score >= 8


class TestMediatorAgent:
    """Test MediatorAgent: conflict detection and proposal generation."""

    @pytest.fixture
    def mediator(self):
        return MediatorAgent()

    def test_detect_conflict_genre_clash(self, mediator):
        """Detect when one user's preference clashes with another's veto."""
        from src.models.schemas import PreferenceVector
        prefs = [
            PreferenceVector(user_name="A", genres=["科幻"], veto_list=[]),
            PreferenceVector(user_name="B", genres=[], veto_list=["科幻"]),
        ]
        conflicts = mediator.detect_conflicts(prefs)
        assert len(conflicts) > 0
        assert any("科幻" in c for c in conflicts)

    def test_detect_conflict_no_conflict(self, mediator):
        """No conflicts when preferences align."""
        from src.models.schemas import PreferenceVector
        prefs = [
            PreferenceVector(user_name="A", genres=["喜剧"], veto_list=[]),
            PreferenceVector(user_name="B", genres=["喜剧"], veto_list=[]),
        ]
        conflicts = mediator.detect_conflicts(prefs)
        assert len(conflicts) == 0

    def test_generate_proposal_returns_valid(self, mediator):
        """Proposal generation should return a valid movie."""
        from src.models.schemas import PreferenceVector
        prefs = [
            PreferenceVector(user_name="A", genres=["喜剧"], max_duration=120),
        ]
        proposal = mediator.generate_proposal(prefs)
        assert proposal is not None
        assert proposal.movie is not None
        assert proposal.movie.duration <= 125  # R2 constraint

    def test_generate_proposal_respects_veto(self, mediator):
        """Proposal should not include vetoed genres."""
        from src.models.schemas import PreferenceVector
        prefs = [
            PreferenceVector(user_name="A", genres=["科幻", "喜剧"]),
            PreferenceVector(user_name="B", veto_list=["科幻"]),
        ]
        proposal = mediator.generate_proposal(prefs)
        assert proposal is not None
        assert "科幻" not in proposal.movie.genres  # Should be filtered out

    def test_generate_proposal_none_for_impossible(self, mediator):
        """Should return None when no movie matches constraints."""
        from src.models.schemas import PreferenceVector
        prefs = [
            PreferenceVector(user_name="A", genres=["科幻"], max_duration=10),
        ]
        proposal = mediator.generate_proposal(prefs)
        assert proposal is None

    def test_tally_votes_calculates_score(self, mediator):
        """Vote tally should calculate group score."""
        from src.models.schemas import VoteResult
        votes = [
            VoteResult(user_name="A", score=8, verdict=Verdict.APPROVE),
            VoteResult(user_name="B", score=6, verdict=Verdict.APPROVE),
        ]
        from src.models.schemas import PreferenceVector
        result = mediator.tally_votes(votes, [PreferenceVector(user_name="A"), PreferenceVector(user_name="B")])
        assert result.group_score == 7.0  # (8+6)/2

    def test_tally_votes_majority_veto(self, mediator):
        """Majority veto should be detected."""
        from src.models.schemas import VoteResult
        votes = [
            VoteResult(user_name="A", score=1, verdict=Verdict.VETO),
            VoteResult(user_name="B", score=1, verdict=Verdict.VETO),
            VoteResult(user_name="C", score=8, verdict=Verdict.APPROVE),
        ]
        from src.models.schemas import PreferenceVector
        result = mediator.tally_votes(votes, [PreferenceVector(user_name="A"), PreferenceVector(user_name="B"), PreferenceVector(user_name="C")])
        assert result.group_score == 0.0
        assert len(result.dissenters) > 0

    def test_safe_fallback(self, mediator):
        """Fallback should return a high-rated comedy."""
        proposal = mediator.apply_safe_fallback()
        assert "喜剧" in proposal.movie.genres
        assert proposal.movie.rating >= 8.0
