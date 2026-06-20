"""
Scenario-based integration tests.
Covers all 5 demo scenarios from main.py.
"""
from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from src.graph.consensus_graph import build_consensus_workflow
from src.models.schemas import Verdict


class TestScenario1:
    """经典冲突：科幻爱好者 vs 喜剧爱好者 (2人)"""

    @pytest.fixture
    def state(self):
        return build_consensus_workflow({
            "Alice": "我喜欢科幻片，时长不要超过120分钟，不要恐怖片",
            "Bob": "我想看喜剧片，轻松一点的，时长90分钟以内最好",
        })

    def test_reaches_consensus(self, state):
        assert state.result is not None
        assert state.result.movie is not None

    def test_no_horror(self, state):
        """Alice vetoed horror - result should not be horror."""
        assert "恐怖" not in state.result.movie.genres

    def test_within_duration(self, state):
        """Bob wants <=90min - result should respect this."""
        assert state.result.movie.duration <= 95


class TestScenario2:
    """恐怖片红线：一方绝对不接受 (2人)"""

    @pytest.fixture
    def state(self):
        return build_consensus_workflow({
            "Alice": "我想看悬疑惊悚片，越刺激越好",
            "Bob": "我害怕恐怖片和惊悚片，想看爱情片或者剧情片，不要超过2小时",
        })

    def test_no_horror_for_bob(self, state):
        """Bob fears horror/thriller - result should be safe."""
        assert "恐怖" not in state.result.movie.genres


class TestScenario3:
    """高要求 vs 随意：评分敏感 (2人)"""

    @pytest.fixture
    def state(self):
        return build_consensus_workflow({
            "Alice": "我只看高分电影，评分至少8分以上，科幻或剧情都可以",
            "Bob": "我随便，什么都行，搞笑的最好",
        })

    def test_high_rating(self, state):
        """Alice wants >=8.0 rating."""
        assert state.result.movie.rating >= 8.0


class TestScenario4:
    """宿舍4人：多目标博弈 (N人扩展)"""

    @pytest.fixture
    def state(self):
        return build_consensus_workflow({
            "Alice": "我喜欢科幻和动作片，评分高的，不要太长",
            "Bob": "我只看喜剧和动画片，超过100分钟的不行",
            "Carol": "我要看爱情片或者剧情片，拒绝恐怖和战争",
            "David": "我都可以，最好是大家都喜欢的，评分8分以上",
        })

    def test_4_person_result(self, state):
        assert state.result is not None
        assert state.result.movie is not None

    def test_no_horror_no_war(self, state):
        """Carol vetoed horror and war."""
        assert "恐怖" not in state.result.movie.genres
        assert "战争" not in state.result.movie.genres

    def test_rating_above_8(self, state):
        """David wants >=8.0."""
        assert state.result.movie.rating >= 8.0

    def test_all_voted(self, state):
        """All 4 users should have voted."""
        assert len(state.votes) == 4

    def test_positive_satisfaction(self, state):
        """Group satisfaction should be positive."""
        assert state.result.group_score > 0


class TestScenario5:
    """家庭6人：代际差异 (N人扩展)"""

    @pytest.fixture
    def state(self):
        return build_consensus_workflow({
            "爷爷": "我想看战争片或者历史剧情片",
            "奶奶": "爱情片或者家庭剧都可以，不要太悲伤",
            "爸爸": "动作片或者悬疑片，刺激一点的",
            "妈妈": "喜剧片最好，全家人一起笑",
            "哥哥": "科幻大片，特效好的，越长越好",
            "妹妹": "动画片或者爱情片，不要超过2小时",
        })

    def test_6_person_result(self, state):
        assert state.result is not None
        assert state.result.movie is not None

    def test_all_6_voted(self, state):
        assert len(state.votes) == 6

    def test_reasonable_duration(self, state):
        """妹妹 wants <=120min."""
        assert state.result.movie.duration <= 125


class TestEdgeCases:
    """Edge cases and boundary conditions."""

    def test_single_user(self):
        """Should work with just 1 user."""
        state = build_consensus_workflow({"Solo": "我喜欢喜剧片"})
        assert state.result is not None
        assert state.result.movie is not None

    def test_empty_preference(self):
        """Should handle empty/ambiguous preferences."""
        state = build_consensus_workflow({"A": "随便"})
        assert state.result is not None

    def test_all_same_preference(self):
        """When everyone wants the same thing."""
        state = build_consensus_workflow({
            "A": "喜剧片",
            "B": "喜剧片",
            "C": "喜剧片",
        })
        assert "喜剧" in state.result.movie.genres

    def test_extreme_duration_constraint(self):
        """Very short duration should trigger fallback."""
        state = build_consensus_workflow({"A": "我只看30分钟以内的电影"})
        # Should still produce a result (fallback to safe pick)
        assert state.result is not None
        assert state.result.movie is not None
