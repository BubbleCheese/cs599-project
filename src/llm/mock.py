"""
Mock LLM Provider - Rule-based fallback when LLM is unavailable.
Uses keyword matching (MVP rule engine) with structured output format.
"""
from __future__ import annotations

import json
import re

from src.llm.base import BaseLLM, LLMConfig, LLMResponse


class MockLLM(BaseLLM):
    """
    Mock LLM that uses rule-based parsing instead of API calls.
    Automatically used when DeepSeek API key is not configured.
    Produces structured output in the same format as real LLM.
    """

    def __init__(self, config: LLMConfig | None = None):
        super().__init__(config)
        self.config.provider = "mock"

    def is_available(self) -> bool:
        return True  # Always available

    def chat(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        """
        Parse the prompt and return structured JSON response.
        Detects which task (preference parsing or voting) based on prompt content.
        """
        content = ""

        if "观影偏好解析" in system_prompt or "genres" in user_prompt:
            content = self._parse_preference(user_prompt)
        elif "观影评价" in system_prompt or "proposal" in user_prompt.lower():
            content = self._vote_on_movie(user_prompt)
        else:
            content = json.dumps({
                "score": 5,
                "verdict": "abstain",
                "reason": "Mock mode: 无法识别的任务类型"
            }, ensure_ascii=False)

        return LLMResponse(content=content, model="mock-rule-engine")

    def _parse_preference(self, prompt: str) -> str:
        """Rule-based preference parsing (same logic as MVP)."""
        # Extract user text from prompt
        match = re.search(r'用户描述："([^"]+)"', prompt)
        text = match.group(1).lower() if match else prompt.lower()

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

        # Veto first (check negation prefix for each genre word)
        veto_list = []
        negation_prefixes = ["不要", "不看", "怕", "拒绝"]
        all_genre_words = {
            "科幻": "科幻", "喜剧": "喜剧", "动作": "动作", "爱情": "爱情",
            "恐怖": "恐怖", "惊悚": "惊悚", "悬疑": "悬疑", "剧情": "剧情",
            "动画": "动画", "奇幻": "奇幻", "冒险": "冒险", "犯罪": "犯罪",
            "音乐": "音乐", "战争": "战争", "纪录片": "纪录片",
        }
        for genre_word, genre_val in all_genre_words.items():
            if genre_word in text and genre_val not in veto_list:
                idx = text.find(genre_word)
                window_start = max(0, idx - 8)
                window = text[window_start:idx]
                if any(p in window for p in negation_prefixes):
                    veto_list.append(genre_val)

        # Genres (skip vetoed)
        genres = []
        for keyword, genre in genre_keywords.items():
            if keyword in text and genre not in genres and genre not in veto_list:
                genres.append(genre)

        if not genres:
            genres = ["剧情"]

        # Duration
        max_duration = 180
        if "90" in text or "一个半小时" in text or "90分钟" in text:
            max_duration = 95
        elif "120" in text or "两小时" in text or "2小时" in text or "120分钟" in text:
            max_duration = 125
        elif "短" in text or "不超过" in text or "以内" in text:
            numbers = re.findall(r'(\d+)', text)
            if numbers:
                max_duration = min(int(numbers[0]) + 5, 180)

        # Min rating
        min_rating = 0.0
        if "高分" in text or "好评" in text or "8分" in text:
            min_rating = 8.0
        elif "7分" in text or "不错" in text:
            min_rating = 7.0

        result = {
            "genres": genres,
            "max_duration": max_duration,
            "min_rating": min_rating,
            "veto_list": veto_list,
            "soft_prefs": text
        }
        return json.dumps(result, ensure_ascii=False)

    def _vote_on_movie(self, prompt: str) -> str:
        """Rule-based voting (same logic as MVP)."""
        # Extract user preferences
        genres_match = re.search(r'喜欢的类型：\[(.*?)\]', prompt)
        genres = [g.strip().strip('"').strip("'") for g in genres_match.group(1).split(",")] if genres_match else []

        max_dur_match = re.search(r'最大时长：(\d+)', prompt)
        max_duration = int(max_dur_match.group(1)) if max_dur_match else 180

        min_rating_match = re.search(r'最低评分：([\d.]+)', prompt)
        min_rating = float(min_rating_match.group(1)) if min_rating_match else 0.0

        veto_match = re.search(r'拒绝的类型：\[(.*?)\]', prompt)
        veto_list = [v.strip().strip('"').strip("'") for v in veto_match.group(1).split(",")] if veto_match and veto_match.group(1) else []

        # Extract movie info
        title_match = re.search(r'片名：(.+)', prompt)
        movie_title = title_match.group(1).strip() if title_match else ""

        mg_match = re.search(r'类型：(.+)', prompt)
        movie_genres = [g.strip() for g in mg_match.group(1).split(",")] if mg_match else []

        md_match = re.search(r'时长：(\d+)', prompt)
        movie_duration = int(md_match.group(1)) if md_match else 120

        mr_match = re.search(r'评分：([\d.]+)', prompt)
        movie_rating = float(mr_match.group(1)) if mr_match else 7.0

        # Veto check
        for veto_genre in veto_list:
            if veto_genre in movie_genres:
                return json.dumps({
                    "score": 1,
                    "verdict": "veto",
                    "reason": f"触及红线：{veto_genre}"
                }, ensure_ascii=False)

        if movie_duration > max_duration:
            return json.dumps({
                "score": 2,
                "verdict": "veto",
                "reason": f"时长超限：{movie_duration}min > {max_duration}min"
            }, ensure_ascii=False)

        # Score calculation
        score = 5
        reasons = []

        matched = [g for g in genres if g in movie_genres]
        if matched:
            score += min(len(matched) * 2, 4)
            reasons.append(f"类型匹配 {matched}")

        if movie_rating >= 9.0:
            score += 2
            reasons.append("高评分")
        elif movie_rating >= 8.0:
            score += 1
            reasons.append("良好评分")

        if movie_duration <= 100:
            score += 1
            reasons.append("时长合适")

        if min_rating > 0 and movie_rating < min_rating:
            score -= 2
            reasons.append(f"评分低于期望 {min_rating}")

        score = max(1, min(10, score))

        if score < 3:
            return json.dumps({
                "score": score,
                "verdict": "veto",
                "reason": f"评分过低：{score}/10"
            }, ensure_ascii=False)

        verdict = "approve" if score >= 6 else "abstain"
        return json.dumps({
            "score": score,
            "verdict": verdict,
            "reason": f"{'赞成' if verdict == 'approve' else '弃权'}：{', '.join(reasons) if reasons else '无明显偏好匹配'} ({score}/10)"
        }, ensure_ascii=False)


def create_llm(config: LLMConfig | None = None) -> BaseLLM:
    """
    Factory function to create LLM provider.
    Priority: DeepSeek (if API key) > Mock (fallback)
    """
    from src.llm.deepseek import DeepSeekLLM

    # Try DeepSeek first
    ds = DeepSeekLLM.from_env()
    if ds.is_available():
        print(f"  [LLM] Using DeepSeek provider (model={ds.config.model})")
        return ds

    # Fallback to mock
    print(f"  [LLM] DeepSeek unavailable, using Mock (rule-based)")
    return MockLLM(config)
