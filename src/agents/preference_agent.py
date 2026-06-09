"""
Preference Agent - Represents a single user's interests.
Supports LLM-powered parsing (DeepSeek) with rule-based fallback.
"""
from __future__ import annotations

import json

from src.models.schemas import PreferenceVector, Movie, Proposal, VoteResult, Verdict
from src.llm.base import BaseLLM
from src.llm.deepseek import PREFERENCE_PARSE_PROMPT, VOTE_PROMPT


class PreferenceAgent:
    """
    Digital spokesperson for a group member.
    LLM-enhanced preference parsing + rule-based voting with LLM augmentation.
    """

    def __init__(self, user_name: str, user_text: str = "", llm: BaseLLM | None = None):
        self.user_name = user_name
        self.raw_input = user_text
        self.preference: PreferenceVector | None = None
        self.llm = llm  # Optional LLM for enhanced parsing

    def declare(self, user_text: str = "") -> PreferenceVector:
        """
        Parse user preference text into structured PreferenceVector.
        
        Strategy:
        1. If LLM available -> use LLM to parse (more accurate)
        2. If LLM unavailable/error -> fallback to rule-based parsing
        """
        text = user_text or self.raw_input

        # Try LLM first
        if self.llm and self.llm.is_available():
            try:
                return self._declare_llm(text)
            except Exception as e:
                print(f"  [LLM parse failed, fallback to rules: {e}]")

        # Fallback: rule-based
        return self._declare_rules(text)

    def _declare_llm(self, text: str) -> PreferenceVector:
        """Use LLM to parse preferences."""
        prompt = PREFERENCE_PARSE_PROMPT.format(user_text=text)
        resp = self.llm.chat(
            system_prompt="你是一个观影偏好解析专家。",
            user_prompt=prompt
        )

        if resp.error:
            raise RuntimeError(f"LLM error: {resp.error}")

        # Parse JSON response
        content = resp.content.strip()
        # Remove markdown code blocks if present
        if content.startswith("```"):
            content = content.split("\n", 1)[1].rsplit("```", 1)[0].strip()

        data = json.loads(content)

        self.preference = PreferenceVector(
            user_name=self.user_name,
            genres=data.get("genres", ["剧情"]),
            max_duration=data.get("max_duration", 180),
            min_rating=data.get("min_rating", 0.0),
            veto_list=data.get("veto_list", []),
            soft_prefs=data.get("soft_prefs", text),
        )
        return self.preference

    def _declare_rules(self, text: str) -> PreferenceVector:
        """Rule-based preference parsing (MVP fallback)."""
        import re
        text_lower = text.lower()

        # Genre mapping
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

        # First: detect vetoed genres (check negation prefix for each genre keyword)
        veto_list = []
        negation_prefixes = ["不要", "不看", "怕", "拒绝"]
        all_genre_words = {
            "科幻": "科幻", "喜剧": "喜剧", "动作": "动作", "爱情": "爱情",
            "恐怖": "恐怖", "惊悚": "惊悚", "悬疑": "悬疑", "剧情": "剧情",
            "动画": "动画", "奇幻": "奇幻", "冒险": "冒险", "犯罪": "犯罪",
            "音乐": "音乐", "战争": "战争", "纪录片": "纪录片",
        }
        # Check each genre word for negation prefix nearby (within 4 chars before)
        for genre_word, genre_val in all_genre_words.items():
            if genre_word in text_lower and genre_val not in veto_list:
                idx = text_lower.find(genre_word)
                window_start = max(0, idx - 8)
                window = text_lower[window_start:idx]
                if any(p in window for p in negation_prefixes):
                    veto_list.append(genre_val)

        # Then: extract preferred genres (skip vetoed ones)
        genres = []
        for keyword, genre in genre_keywords.items():
            if keyword in text_lower and genre not in genres and genre not in veto_list:
                genres.append(genre)

        if not genres:
            genres = ["剧情"]

        # Duration
        max_duration = 180
        if "90" in text_lower or "一个半小时" in text_lower or "90分钟" in text_lower:
            max_duration = 95
        elif "120" in text_lower or "两小时" in text_lower or "2小时" in text_lower or "120分钟" in text_lower:
            max_duration = 125
        elif "短" in text_lower or "不超过" in text_lower or "以内" in text_lower:
            numbers = re.findall(r'(\d+)', text_lower)
            if numbers:
                max_duration = min(int(numbers[0]) + 5, 180)

        # Min rating
        min_rating = 0.0
        if "高分" in text_lower or "好评" in text_lower or "8分" in text_lower:
            min_rating = 8.0
        elif "7分" in text_lower or "不错" in text_lower:
            min_rating = 7.0

        self.preference = PreferenceVector(
            user_name=self.user_name,
            genres=genres,
            max_duration=max_duration,
            min_rating=min_rating,
            veto_list=veto_list,
            soft_prefs=text,
        )
        return self.preference

    def vote(self, proposal: Proposal) -> VoteResult:
        """
        Vote on a proposal.
        Strategy:
        1. Hard constraints (veto) - always rule-based (fast, deterministic)
        2. Scoring - try LLM first, fallback to rules
        """
        if self.preference is None:
            raise RuntimeError("Preference not declared. Call declare() first.")

        movie = proposal.movie
        p = self.preference

        # V1: Hard constraint check (always rule-based)
        for veto_genre in p.veto_list:
            if veto_genre in movie.genres:
                return VoteResult(
                    user_name=self.user_name,
                    score=1,
                    verdict=Verdict.VETO,
                    reason=f"V1-硬约束冲突：触及红线 '{veto_genre}'"
                )

        # V1: Duration check
        if movie.duration > p.max_duration:
            return VoteResult(
                user_name=self.user_name,
                score=2,
                verdict=Verdict.VETO,
                reason=f"V1-时长超限：{movie.duration}min > 上限 {p.max_duration}min"
            )

        # Try LLM for nuanced scoring (skip if mock provider - use rules directly)
        if self.llm and self.llm.is_available() and getattr(self.llm.config, 'provider', '') != 'mock':
            try:
                return self._vote_llm(proposal)
            except Exception:
                pass  # Fallback to rules

        return self._vote_rules(proposal)

    def _vote_llm(self, proposal: Proposal) -> VoteResult:
        """Use LLM for nuanced voting."""
        p = self.preference
        movie = proposal.movie

        prompt = VOTE_PROMPT.format(
            genres=p.genres,
            max_duration=p.max_duration,
            min_rating=p.min_rating,
            veto_list=p.veto_list,
            soft_prefs=p.soft_prefs,
            movie_title=movie.title,
            movie_genres=movie.genres,
            movie_duration=movie.duration,
            movie_rating=movie.rating,
            movie_description=movie.description,
        )

        resp = self.llm.chat(
            system_prompt="你是一个观影评价助手。",
            user_prompt=prompt
        )

        if resp.error:
            raise RuntimeError(resp.error)

        content = resp.content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1].rsplit("```", 1)[0].strip()

        data = json.loads(content)
        score = max(1, min(10, int(data.get("score", 5))))
        verdict_str = data.get("verdict", "abstain")

        # Map string to enum
        verdict_map = {"approve": Verdict.APPROVE, "veto": Verdict.VETO, "abstain": Verdict.ABSTAIN}
        verdict = verdict_map.get(verdict_str, Verdict.ABSTAIN)

        return VoteResult(
            user_name=self.user_name,
            score=score,
            verdict=verdict,
            reason=data.get("reason", "LLM 评价") + " [LLM]",
        )

    def _vote_rules(self, proposal: Proposal) -> VoteResult:
        """Rule-based scoring (MVP fallback)."""
        movie = proposal.movie
        p = self.preference

        score = 5
        reasons = []

        matched_genres = [g for g in p.genres if g in movie.genres]
        if matched_genres:
            score += min(len(matched_genres) * 2, 4)
            reasons.append(f"类型匹配 {matched_genres}")

        if movie.rating >= 9.0:
            score += 2
            reasons.append("高评分")
        elif movie.rating >= 8.0:
            score += 1
            reasons.append("良好评分")

        if movie.duration <= 100:
            score += 1
            reasons.append("时长合适")

        if p.min_rating > 0 and movie.rating < p.min_rating:
            score -= 2
            reasons.append(f"评分低于期望 {p.min_rating}")

        score = max(1, min(10, score))

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
            reason=f"{'赞成' if verdict == Verdict.APPROVE else '弃权'}：{', '.join(reasons) if reasons else '无明显偏好匹配'} ({score}/10)"
        )

    def __repr__(self) -> str:
        llm_status = "LLM" if self.llm and self.llm.is_available() else "rule"
        return f"PreferenceAgent({self.user_name}, {llm_status})"
