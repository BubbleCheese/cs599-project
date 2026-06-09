"""
DeepSeek LLM Provider
Uses OpenAI-compatible API to call DeepSeek models.
"""
from __future__ import annotations

import os
from typing import Optional

from src.llm.base import BaseLLM, LLMConfig, LLMResponse


class DeepSeekLLM(BaseLLM):
    """
    DeepSeek API provider.
    Compatible with OpenAI API format.
    
    Setup:
        export DEEPSEEK_API_KEY="your-key"
        # or set in .env file
    
    Usage:
        llm = DeepSeekLLM.from_env()
        resp = llm.chat("System prompt", "User prompt")
    """

    def __init__(self, config: LLMConfig | None = None):
        super().__init__(config)
        self.config.provider = "deepseek"
        self.config.base_url = self.config.base_url or "https://api.deepseek.com/v1"
        self.config.model = self.config.model or "deepseek-chat"
        self._client = None
        self._init_client()

    def _init_client(self) -> None:
        """Initialize OpenAI client for DeepSeek."""
        if not self.config.api_key:
            self._client = None
            return
        try:
            from openai import OpenAI
            self._client = OpenAI(
                api_key=self.config.api_key,
                base_url=self.config.base_url,
                timeout=self.config.timeout,
            )
        except ImportError:
            self._client = None

    @classmethod
    def from_env(cls) -> DeepSeekLLM:
        """Create instance from environment variables."""
        api_key = os.environ.get("DEEPSEEK_API_KEY", "")
        base_url = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
        return cls(LLMConfig(
            provider="deepseek",
            api_key=api_key if api_key else None,
            base_url=base_url,
        ))

    def is_available(self) -> bool:
        """Check if DeepSeek API key is configured."""
        if self._client is None:
            return False
        if not self.config.api_key:
            return False
        return True

    def chat(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        """Call DeepSeek API with retry."""
        if not self.is_available():
            return LLMResponse(
                content="",
                error="DeepSeek API not available. Check DEEPSEEK_API_KEY."
            )

        messages = self._build_messages(system_prompt, user_prompt)

        # Retry logic
        max_retries = 2
        for attempt in range(max_retries + 1):
            try:
                resp = self._client.chat.completions.create(
                    model=self.config.model,
                    messages=messages,
                    temperature=self.config.temperature,
                    max_tokens=self.config.max_tokens,
                )
                return LLMResponse(
                    content=resp.choices[0].message.content or "",
                    model=resp.model or self.config.model,
                    usage={
                        "prompt_tokens": resp.usage.prompt_tokens if resp.usage else 0,
                        "completion_tokens": resp.usage.completion_tokens if resp.usage else 0,
                    }
                )
            except Exception as e:
                if attempt < max_retries:
                    continue
                return LLMResponse(
                    content="",
                    error=f"DeepSeek API error: {type(e).__name__}: {e}"
                )
        return LLMResponse(content="", error="Max retries exceeded")


# ===== Prompt Templates for Preference Agent =====

PREFERENCE_PARSE_PROMPT = """你是一个观影偏好解析专家。请根据用户的自然语言描述，提取以下结构化信息，以 JSON 格式返回。

用户描述："{user_text}"

请返回严格符合以下格式的 JSON（不要包含任何其他文字）：
{{
    "genres": ["类型1", "类型2"],
    "max_duration": 120,
    "min_rating": 8.0,
    "veto_list": ["不要的类型1"],
    "soft_prefs": "用户的原始描述"
}}

规则：
- genres：从用户描述中提取偏好的电影类型（如科幻、喜剧、动作、爱情、恐怖、悬疑、剧情、动画、奇幻、冒险、犯罪、音乐、战争、纪录片）
- max_duration：用户能接受的最大时长（分钟），默认180
- min_rating：用户要求的最低评分（0-10），默认0
- veto_list：用户明确拒绝的类型
- soft_prefs：保留用户原始描述中的其他偏好信息

注意：只返回 JSON，不要 markdown 代码块，不要解释。"""


VOTE_PROMPT = """你是一个观影评价助手。请根据用户的偏好和当前提案影片，给出评价。

用户偏好：
- 喜欢的类型：{genres}
- 最大时长：{max_duration}分钟
- 最低评分：{min_rating}
- 拒绝的类型：{veto_list}
- 其他偏好：{soft_prefs}

提案影片：
- 片名：{movie_title}
- 类型：{movie_genres}
- 时长：{movie_duration}分钟
- 评分：{movie_rating}/10
- 简介：{movie_description}

请返回严格 JSON 格式：
{{
    "score": 7,
    "verdict": "approve",
    "reason": "评价理由"
}}

verdict 只能是：approve（赞成，score>=6）、veto（否决，触及红线）、abstain（弃权，score<6）
score 范围 1-10。

只返回 JSON，不要其他内容。"""
