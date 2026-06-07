"""
Mediator Agent - Central coordinator for group consensus.
Detects conflicts, applies compromise rules, generates proposals,
and makes final decisions based on voting results.
"""
from __future__ import annotations

from typing import List

from src.models.schemas import (
    PreferenceVector, Movie, Proposal, VoteResult, ConsensusResult,
    Verdict
)
from src.data.movies import search_movies, get_safe_pick


class MediatorAgent:
    """
    Smart meeting moderator that coordinates between PreferenceAgents.
    
    Responsibilities:
    1. Detect conflicts between user preferences
    2. Apply compromise rules (R1-R5) to find common ground
    3. Generate movie proposals that maximize group satisfaction
    4. Aggregate votes and make final decisions
    """

    def __init__(self):
        self.conflicts_log: List[str] = []
        self.rules_log: List[str] = []
    
    def detect_conflicts(self, preferences: List[PreferenceVector]) -> List[str]:
        """
        Detect irreconcilable conflicts among preferences.
        Returns list of conflict descriptions.
        """
        conflicts = []
        n = len(preferences)
        
        for i in range(n):
            for j in range(i + 1, n):
                p1, p2 = preferences[i], preferences[j]
                
                # Check genre clash: P1's preference vs P2's veto
                for g in p1.genres:
                    if g in p2.veto_list:
                        conflicts.append(f"类型冲突：{p1.user_name}偏好'{g}'但{p2.user_name}拒绝该类型")
                for g in p2.genres:
                    if g in p1.veto_list:
                        conflicts.append(f"类型冲突：{p2.user_name}偏好'{g}'但{p1.user_name}拒绝该类型")
                
                # Check duration conflict
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
        Generate movie proposal by applying compromise rules in priority order.
        Returns None if no proposal can be generated.
        """
        exclude_ids = exclude_movie_ids or []
        
        # === R1: Genre intersection ===
        # Find genres that are preferred by at least one user and not vetoed by any
        safe_genres = set()
        for p in preferences:
            for g in p.genres:
                # Check if any other user vetoes this genre
                vetoed = any(g in other.veto_list for other in preferences if other.user_name != p.user_name)
                if not vetoed:
                    safe_genres.add(g)
        
        # Also consider cross-genre movies (e.g., 科幻+动作)
        all_preferred = set()
        for p in preferences:
            all_preferred.update(p.genres)
        
        # Collect all genres that appear in any user's preference or are cross-compatible
        candidate_genres = list(safe_genres) if safe_genres else list(all_preferred)
        
        # === R2: Duration minimum (strictest constraint wins) ===
        # Use the minimum max_duration across all users (most restrictive wins)
        min_max_duration = min(p.max_duration for p in preferences)
        max_dur = min_max_duration + 5  # 5min buffer for strictest user
        
        # === R3: Min rating max ===
        min_rating = max(p.min_rating for p in preferences)
        
        # === Build exclusion list ===
        all_veto_genres = []
        for p in preferences:
            all_veto_genres.extend(p.veto_list)
        
        # Search with compromise parameters
        candidates = search_movies(
            genres=candidate_genres if candidate_genres else None,
            max_duration=max_dur,
            min_rating=min_rating,
            exclude_genres=list(set(all_veto_genres)),
            exclude_ids=exclude_ids,
            limit=5
        )
        
        if candidates:
            # Pick the highest-rated candidate
            movie = candidates[0]
            rules_applied = []
            if len(preferences) > 1 and len(safe_genres) < len(all_preferred):
                rules_applied.append("R1-类型交叉（过滤了冲突类型）")
            else:
                rules_applied.append("R1-类型交集")
            rules_applied.append(f"R2-时长约束 {min_max_duration}min")
            if min_rating > 0:
                rules_applied.append(f"R3-评分阈值 {min_rating}")
            
            self.rules_log.extend(rules_applied)
            
            return Proposal(
                movie=movie,
                compromise_rules_applied=rules_applied,
                reason=f"基于类型交集的妥协方案，从 {len(candidates)} 部候选中选出评分最高者",
                round_num=round_num
            )
        
        return None
    
    def apply_safe_fallback(self) -> Proposal:
        """
        R5: Safe card fallback - recommend a highly-rated comedy.
        Called when all other rules fail.
        """
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
        """
        Aggregate votes and produce final consensus result.
        
        Checks:
        - V3: Majority veto (>50% explicit veto)
        - Overall group satisfaction score
        """
        total = len(votes)
        vetoes = [v for v in votes if v.verdict == Verdict.VETO]
        approves = [v for v in votes if v.verdict == Verdict.APPROVE]
        abstains = [v for v in votes if v.verdict == Verdict.ABSTAIN]
        
        # V3: Majority veto
        if len(vetoes) > total / 2:
            return ConsensusResult(
                movie=None,
                group_score=0.0,
                votes=votes,
                negotiation_log=[f"V3-多数否决：{len(vetoes)}/{total} 成员否决"],
                dissenters=[v.user_name for v in vetoes]
            )
        
        # Calculate group score (average of approve scores, veto counts as 0)
        group_score = sum(v.score for v in votes) / total if total > 0 else 0
        
        # Determine dissenters (those who vetoed or abstained with low score)
        dissenters = [v.user_name for v in votes if v.verdict == Verdict.VETO or v.score < 5]
        
        return ConsensusResult(
            movie=None,  # Will be filled by the caller
            group_score=group_score,
            votes=votes,
            dissenters=dissenters
        )
    
    def finalize(
        self,
        proposal: Proposal,
        votes: List[VoteResult]
    ) -> ConsensusResult:
        """
        Make final decision based on proposal and votes.
        If votes are mixed, Mediator has the authority to decide.
        """
        result = self.tally_votes(votes, [])
        result.movie = proposal.movie
        result.negotiation_log = self.rules_log + [v.reason for v in votes]
        result.rounds_taken = proposal.round_num
        result.is_fallback = proposal.round_num >= 99
        
        return result

    def __repr__(self) -> str:
        return "MediatorAgent()"
