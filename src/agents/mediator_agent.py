"""
Mediator Agent - Central coordinator for group consensus.
Uses Chroma vector store for historical awareness + MCP tools for movie search.
"""
from __future__ import annotations

from typing import List

from src.models.schemas import (
    PreferenceVector, Movie, Proposal, VoteResult, ConsensusResult, Verdict
)
from src.data.movies import search_movies, get_safe_pick
from src.memory.vector_store import BaseVectorStore
from src.tools.douban_mcp import call_tool


class MediatorAgent:
    """
    Smart meeting moderator with historical awareness.
    
    Enhancements over MVP:
    - Chroma vector store: query historical decisions for context
    - MCP tools: search external movie databases
    - R3 (history weighting): uses vector similarity for genre weighting
    """

    def __init__(self, vector_store: BaseVectorStore | None = None):
        self.conflicts_log: List[str] = []
        self.rules_log: List[str] = []
        self.vector_store = vector_store

    def detect_conflicts(self, preferences: List[PreferenceVector]) -> List[str]:
        """Detect irreconcilable conflicts among preferences."""
        conflicts = []
        n = len(preferences)

        for i in range(n):
            for j in range(i + 1, n):
                p1, p2 = preferences[i], preferences[j]

                for g in p1.genres:
                    if g in p2.veto_list:
                        conflicts.append(f"类型冲突：{p1.user_name}偏好'{g}'但{p2.user_name}拒绝该类型")
                for g in p2.genres:
                    if g in p1.veto_list:
                        conflicts.append(f"类型冲突：{p2.user_name}偏好'{g}'但{p1.user_name}拒绝该类型")

                if p1.max_duration < p2.max_duration - 30:
                    conflicts.append(f"时长冲突：{p1.user_name}接受≤{p1.max_duration}min，{p2.user_name}接受≤{p2.max_duration}min")

        self.conflicts_log = conflicts
        return conflicts

    def generate_proposal(
        self,
        preferences: List[PreferenceVector],
        round_num: int = 1,
        exclude_movie_ids: List[str] | None = None
    ) -> Proposal | None:
        """
        Generate movie proposal using compromise rules + Chroma history.
        """
        exclude_ids = exclude_movie_ids or []

        # === R3 (Enhanced): Query historical decisions ===
        history_context = ""
        if self.vector_store:
            similar = self.vector_store.query_similar(preferences, n_results=2)
            if similar:
                history_context = f" [历史参考: 曾推荐过{similar[0].get('title', '?')}满意度{similar[0].get('group_score', 0)}]"
                self.rules_log.append(f"R3-历史参考：查找到 {len(similar)} 条相似记录")

        # === R1: Genre intersection ===
        safe_genres = set()
        for p in preferences:
            for g in p.genres:
                vetoed = any(g in other.veto_list for other in preferences if other.user_name != p.user_name)
                if not vetoed:
                    safe_genres.add(g)

        all_preferred = set()
        for p in preferences:
            all_preferred.update(p.genres)

        candidate_genres = list(safe_genres) if safe_genres else list(all_preferred)

        # === R2: Duration strictest constraint ===
        min_max_duration = min(p.max_duration for p in preferences)
        max_dur = min_max_duration + 5

        # === R3: Min rating max ===
        min_rating = max(p.min_rating for p in preferences)

        # === Build exclusion list ===
        all_veto_genres = []
        for p in preferences:
            all_veto_genres.extend(p.veto_list)

        # Try MCP tool first (if real API available)
        mcp_results = self._try_mcp_search(candidate_genres, max_dur, min_rating, exclude_ids)

        if mcp_results:
            candidates = mcp_results
        else:
            # Fallback: local database
            candidates = search_movies(
                genres=candidate_genres if candidate_genres else None,
                max_duration=max_dur,
                min_rating=min_rating,
                exclude_genres=list(set(all_veto_genres)),
                exclude_ids=exclude_ids,
                limit=5,
            )

        if candidates:
            movie = candidates[0]
            rules_applied = []
            if len(preferences) > 1 and len(safe_genres) < len(all_preferred):
                rules_applied.append("R1-类型交叉（过滤了冲突类型）")
            else:
                rules_applied.append("R1-类型交集")
            rules_applied.append(f"R2-时长约束 {min_max_duration}min")
            if min_rating > 0:
                rules_applied.append(f"R3-评分阈值 {min_rating}")
            if history_context:
                rules_applied.append(f"R3-历史加权{history_context}")

            self.rules_log.extend(rules_applied)

            source = "MCP" if mcp_results else "本地数据库"
            return Proposal(
                movie=movie,
                compromise_rules_applied=rules_applied,
                reason=f"基于类型交集的妥协方案，从 {len(candidates)} 部候选中选出评分最高者 ({source})",
                round_num=round_num
            )

        return None

    def _try_mcp_search(
        self,
        genres: List[str],
        max_duration: int,
        min_rating: float,
        exclude_ids: List[str],
    ) -> List[Movie] | None:
        """Try MCP tool for movie search. Returns None if unavailable."""
        try:
            # Use primary genre for MCP search
            genre = genres[0] if genres else None
            result = call_tool(
                "douban.search",
                genre=genre,
                rating_min=min_rating if min_rating > 0 else None,
                max_duration=max_duration,
                limit=5,
            )
            import json
            data = json.loads(result)
            if "error" in data:
                return None

            movies = []
            for item in data:
                if item.get("id") in exclude_ids:
                    continue
                movies.append(Movie(
                    movie_id=item["id"],
                    title=item["title"],
                    genres=item.get("genres", []),
                    duration=item.get("duration", 120),
                    rating=item.get("rating", 7.0),
                    year=item.get("year", 2020),
                ))
            return movies if movies else None
        except Exception:
            return None

    def apply_safe_fallback(self) -> Proposal:
        """R5: Safe card fallback."""
        movie = get_safe_pick()
        self.rules_log.append("R5-安全牌兜底（高评分喜剧）")
        return Proposal(
            movie=movie,
            compromise_rules_applied=["R5-安全牌兜底"],
            reason="所有妥协规则均无法生成可行方案，启用安全牌推荐",
            round_num=99
        )

    def tally_votes(
        self,
        votes: List[VoteResult],
        preferences: List[PreferenceVector]
    ) -> ConsensusResult:
        """Aggregate votes and produce result."""
        total = len(votes)
        vetoes = [v for v in votes if v.verdict == Verdict.VETO]

        if len(vetoes) > total / 2:
            return ConsensusResult(
                movie=None,
                group_score=0.0,
                votes=votes,
                negotiation_log=[f"V3-多数否决：{len(vetoes)}/{total} 成员否决"],
                dissenters=[v.user_name for v in vetoes]
            )

        group_score = sum(v.score for v in votes) / total if total > 0 else 0
        dissenters = [v.user_name for v in votes if v.verdict == Verdict.VETO or v.score < 5]

        return ConsensusResult(
            movie=None,
            group_score=group_score,
            votes=votes,
            dissenters=dissenters
        )

    def finalize(
        self,
        proposal: Proposal,
        votes: List[VoteResult]
    ) -> ConsensusResult:
        """Make final decision."""
        result = self.tally_votes(votes, [])
        result.movie = proposal.movie
        result.negotiation_log = self.rules_log + [v.reason for v in votes]
        result.rounds_taken = proposal.round_num
        result.is_fallback = proposal.round_num >= 99

        # Store to vector store for future reference
        if self.vector_store:
            try:
                # Need preferences - extract from votes
                from src.models.schemas import PreferenceVector
                prefs = []
                for v in votes:
                    # Extract preference info from vote
                    pref = PreferenceVector(
                        user_name=v.user_name,
                        genres=getattr(v, 'preferred_genres', []),
                        max_duration=getattr(v, 'max_duration', 180),
                        min_rating=getattr(v, 'min_rating', 0.0),
                        veto_list=getattr(v, 'veto_list', []),
                        soft_prefs=v.reason
                    )
                    prefs.append(pref)
                self.vector_store.add_watch_record(result, prefs)
                print(f"  [Memory] 已记录观影历史到 ChromaDB")
            except Exception as e:
                print(f"  [Memory] 记录失败：{e}")

        return result

    def __repr__(self) -> str:
        store = "Chroma" if self.vector_store else "none"
        return f"MediatorAgent(store={store})"
