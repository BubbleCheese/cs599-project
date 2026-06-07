"""
Preference Agent - Represents a single user's interests.
Parses natural language preferences into structured vectors,
maintains hard constraints, and votes on proposals.
"""
from __future__ import annotations

from src.models.schemas import PreferenceVector, Movie, Proposal, VoteResult, Verdict


class PreferenceAgent:
    """
    Digital spokesperson for a group member.
    
    Responsibilities:
    1. Parse natural language preferences into structured PreferenceVector
    2. Maintain hard constraints (red lines) and soft preferences
    3. Vote on proposals with score + qualitative feedback
    4. Exercise veto power when red lines are crossed
    """

    def __init__(self, user_name: str, user_text: str = ""):
        self.user_name = user_name
        self.raw_input = user_text
        self.preference: PreferenceVector | None = None
    
    def declare(self, user_text: str = "") -> PreferenceVector:
        """
        Parse user preference text into structured PreferenceVector.
        
        MVP: Rule-based NLP parsing (no LLM required).
        Maps keywords to genres, duration limits, and constraints.
        """
        text = (user_text or self.raw_input).lower()
        
        # Genre mapping (中文关键词 -> genre tags)
        genre_keywords = {
            "科幻": "科幻", "sci-fi": "科幻", "未来": "科幻",
            "喜剧": "喜剧", "搞笑": "喜剧", "幽默": "喜剧",
            "动作": "动作", "打斗": "动作", "枪战": "动作",
            "爱情": "爱情", "浪漫": "爱情", "恋爱": "爱情",
            "恐怖": "恐怖", "惊悚": "惊悚", "悬疑": "悬疑",
            "剧情": "剧情", "文艺": "剧情",
            "动画": "动画", "动漫": "动画", "卡通": "动画",
            "奇幻": "奇幻", "魔幻": "奇幻", "冒险": "冒险",
            "犯罪": "犯罪", "警匪": "犯罪",
            "音乐": "音乐", "歌舞": "音乐",
            "战争": "战争",
            "纪录片": "纪录片", "纪录": "纪录片",
        }
        
        genres = []
        for keyword, genre in genre_keywords.items():
            if keyword in text and genre not in genres:
                genres.append(genre)
        
        # Default genre if none detected
        if not genres:
            genres = ["剧情"]
        
        # Duration constraint parsing
        max_duration = 180  # default
        if "90" in text or "一个半小时" in text or "90分钟" in text:
            max_duration = 95
        elif "120" in text or "两小时" in text or "120分钟" in text:
            max_duration = 125
        elif "短" in text or "不超过" in text:
            # Try to extract number
            import re
            numbers = re.findall(r'(\d+)', text)
            if numbers:
                max_duration = min(int(numbers[0]) + 5, 180)
        
        # Veto list (hard constraints)
        veto_list = []
        veto_keywords = {
            "不要恐怖": "恐怖", "怕恐怖": "恐怖", "不看恐怖": "恐怖",
            "不要惊悚": "惊悚", "不看惊悚": "惊悚",
            "不要血腥": "恐怖", "不看血腥": "恐怖",
            "不要战争": "战争", "不看战争": "战争",
        }
        for keyword, veto_genre in veto_keywords.items():
            if keyword in text and veto_genre not in veto_list:
                veto_list.append(veto_genre)
        
        # Min rating
        min_rating = 0.0
        if "高分" in text or "好评" in text or "8分" in text:
            min_rating = 8.0
        elif "7分" in text or "不错" in text:
            min_rating = 7.0
        
        self.preference = PreferenceVector(
            user_name=self.user_name,
            genres=genres,
            max_duration=max_duration,
            min_rating=min_rating,
            veto_list=veto_list,
            soft_prefs=text
        )
        return self.preference
    
    def vote(self, proposal: Proposal) -> VoteResult:
        """
        Vote on a proposal. 
        
        Returns APPROVE (score >= 6), VETO (red line crossed), or ABSTAIN.
        MVP: Rule-based scoring without LLM.
        """
        if self.preference is None:
            raise RuntimeError("Preference not declared. Call declare() first.")
        
        movie = proposal.movie
        p = self.preference
        
        # V1: Hard constraint check
        for veto_genre in p.veto_list:
            if veto_genre in movie.genres:
                return VoteResult(
                    user_name=self.user_name,
                    score=1,
                    verdict=Verdict.VETO,
                    reason=f"V1-硬约束冲突：触及红线 '{veto_genre}'"
                )
        
        # V2: Duration check (treat as hard constraint if max_duration specified)
        if movie.duration > p.max_duration:
            return VoteResult(
                user_name=self.user_name,
                score=2,
                verdict=Verdict.VETO,
                reason=f"V1-时长超限：{movie.duration}min > 上限 {p.max_duration}min"
            )
        
        # Score calculation (1-10)
        score = 5  # base score
        reasons = []
        
        # Genre match bonus
        matched_genres = [g for g in p.genres if g in movie.genres]
        if matched_genres:
            score += min(len(matched_genres) * 2, 4)
            reasons.append(f"类型匹配 {matched_genres}")
        
        # Rating bonus
        if movie.rating >= 9.0:
            score += 2
            reasons.append("高评分")
        elif movie.rating >= 8.0:
            score += 1
            reasons.append("良好评分")
        
        # Duration preference bonus
        if movie.duration <= 100:
            score += 1
            reasons.append("时长合适")
        
        # Min rating check (soft constraint)
        if p.min_rating > 0 and movie.rating < p.min_rating:
            score -= 2
            reasons.append(f"评分低于期望 {p.min_rating}")
        
        score = max(1, min(10, score))
        
        # V2: Score below threshold
        if score < 3:
            return VoteResult(
                user_name=self.user_name,
                score=score,
                verdict=Verdict.VETO,
                reason=f"V2-评分过低：{score}/10 ({', '.join(reasons)})"
            )
        
        verdict = Verdict.APPROVE if score >= 6 else Verdict.ABSTAIN
        return VoteResult(
            user_name=self.user_name,
            score=score,
            verdict=verdict,
            reason=f"{'赞成' if verdict == Verdict.APPROVE else '弃权'}：{', '.join(reasons) if reasons else '无明显偏好匹配'} (评分 {score}/10)"
        )

    def __repr__(self) -> str:
        return f"PreferenceAgent({self.user_name})"
