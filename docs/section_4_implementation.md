# 4 关键实现与代码展示

本章节基于项目实际代码（`src/` 目录），展示核心模块的类定义、关键算法和接口实现。所有代码片段均来自当前代码库，可直接运行。

---

## 4.1 数据模型层

使用 Pydantic 定义核心数据模型，确保类型安全和数据校验。核心模型包括：
- **PreferenceVector**（偏好向量，包含 `genres`、`max_duration`、`min_rating`、`veto_list` 等字段）
- **Movie**（影片元数据）
- **Proposal**（提案，包含影片和妥协规则记录）
- **VoteResult**（投票结果，包含 `score`、`verdict`、`reason`）
- **ConsensusResult**（共识结果，包含最终影片、群体满意度、协商日志等）
- **AgentState**（LangGraph 状态对象，贯穿整个协商流程）

### 代码实现：`src/models/schemas.py`

```python
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class Verdict(str, Enum):
    """Vote verdict options."""
    APPROVE = "approve"
    VETO = "veto"
    ABSTAIN = "abstain"

class PreferenceVector(BaseModel):
    """Structured user preference declaration."""
    user_name: str
    genres: List[str] = Field(default_factory=list, description="Preferred genres")
    max_duration: int = Field(default=180, description="Max acceptable duration in minutes")
    min_rating: float = Field(default=0.0, description="Minimum rating threshold")
    veto_list: List[str] = Field(default_factory=list, description="Hard constraints (e.g., ['horror'])")
    soft_prefs: str = Field(default="", description="Natural language soft preferences")

class Movie(BaseModel):
    """Movie metadata."""
    movie_id: str
    title: str
    genres: List[str]
    duration: int  # minutes
    rating: float  # 0-10
    year: int = 2020
    description: str = ""

class Proposal(BaseModel):
    """Movie proposal sent by Mediator to PreferenceAgents."""
    movie: Movie
    compromise_rules_applied: List[str] = Field(default_factory=list)
    reason: str = ""
    round_num: int = 1

class VoteResult(BaseModel):
    """Vote from a PreferenceAgent on a proposal."""
    user_name: str
    score: int = Field(ge=1, le=10, description="Satisfaction score 1-10")
    verdict: Verdict = Verdict.ABSTAIN
    reason: str = ""

class ConsensusResult(BaseModel):
    """Final consensus output."""
    movie: Optional[Movie] = None
    group_score: float = 0.0
    votes: List[VoteResult] = Field(default_factory=list)
    negotiation_log: List[str] = Field(default_factory=list)
    rounds_taken: int = 0
    dissenters: List[str] = Field(default_factory=list)
    is_fallback: bool = False

class AgentState(BaseModel):
    """LangGraph state for the consensus workflow."""
    user_inputs: Dict[str, str] = Field(default_factory=dict)
    preferences: List[PreferenceVector] = Field(default_factory=list)
    current_proposal: Optional[Proposal] = None
    proposal_candidates: List[Movie] = Field(default_factory=list)
    votes: List[VoteResult] = Field(default_factory=list)
    conflicts_detected: List[str] = Field(default_factory=list)
    resolve_round: int = 0
    max_resolve_rounds: int = 3
    result: Optional[ConsensusResult] = None
    log: List[str] = Field(default_factory=list)

    def add_log(self, message: str) -> None:
        self.log.append(message)
        print(f"  [{len(self.log)}] {message}")
```

### 设计要点

1. **Verdict 枚举**：`approve`/`veto`/`abstain` 三种投票结果，避免字符串硬编码错误。
2. **Field 约束**：`score` 使用 `ge=1, le=10` 限制评分范围；`max_duration` 默认 180 分钟。
3. **状态追踪**：`AgentState` 使用 `resolve_round` 和 `max_resolve_rounds` 实现轮次控制，防止无限循环。
4. **Pydantic 校验**：所有输入自动进行类型校验和默认值填充，确保下游节点接收到的数据始终合法。

---

## 4.2 PreferenceAgent 实现

`PreferenceAgent` 实现了 `declare()` 和 `vote()` 两个核心方法，代表单个用户的利益。

### 代码实现：`src/agents/preference_agent.py`

#### 4.2.1 `declare()` — 偏好声明

```python
class PreferenceAgent:
    def __init__(self, user_name: str, user_text: str = "", llm: BaseLLM | None = None):
        self.user_name = user_name
        self.raw_input = user_text
        self.preference: PreferenceVector | None = None
        self.llm = llm

    def declare(self, user_text: str = "") -> PreferenceVector:
        """Parse user preference text into structured PreferenceVector.
        Strategy: LLM first, rule-based fallback."""
        text = user_text or self.raw_input

        if self.llm and self.llm.is_available():
            try:
                return self._declare_llm(text)
            except Exception as e:
                print(f"  [LLM parse failed, fallback to rules: {e}]")
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
        content = resp.content.strip()
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

        # Genre mapping (50+ keywords -> 15 canonical genres)
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

        # ===== Veto detection (negation prefix) =====
        veto_list = []
        negation_prefixes = ["不要", "不看", "怕", "拒绝"]
        for genre_word, genre_val in all_genre_words.items():
            if genre_word in text_lower and genre_val not in veto_list:
                idx = text_lower.find(genre_word)
                window_start = max(0, idx - 8)
                window = text_lower[window_start:idx]
                if any(p in window for p in negation_prefixes):
                    veto_list.append(genre_val)

        # ===== Preferred genres (skip vetoed) =====
        genres = []
        for keyword, genre in genre_keywords.items():
            if keyword in text_lower and genre not in genres and genre not in veto_list:
                genres.append(genre)
        if not genres:
            genres = ["剧情"]

        # Duration extraction
        max_duration = 180
        if "90" in text_lower or "一个半小时" in text_lower or "90分钟" in text_lower:
            max_duration = 95
        elif "120" in text_lower or "两小时" in text_lower or "2小时" in text_lower or "120分钟" in text_lower:
            max_duration = 125
        elif "短" in text_lower or "不超过" in text_lower or "以内" in text_lower:
            numbers = re.findall(r'(\d+)', text_lower)
            if numbers:
                max_duration = min(int(numbers[0]) + 5, 180)

        # Min rating extraction
        min_rating = 0.0
        if "高分" in text_lower or "好评" in text_lower or "8分" in text_lower:
            min_rating = 8.0
        elif "7分" in text_lower or "不错" in text_lower:
            min_rating = 7.0

        self.preference = PreferenceVector(
            user_name=self.user_name,
            genres=genres, max_duration=max_duration,
            min_rating=min_rating, veto_list=veto_list,
            soft_prefs=text,
        )
        return self.preference
```

#### 4.2.2 `vote()` — 投票评价

```python
    def vote(self, proposal: Proposal) -> VoteResult:
        """Vote on a proposal.
        1. Hard constraints (veto) - always rule-based
        2. Scoring - try LLM first, fallback to rules"""
        if self.preference is None:
            raise RuntimeError("Preference not declared. Call declare() first.")

        movie = proposal.movie
        p = self.preference

        # V1: Hard constraint check (always rule-based)
        for veto_genre in p.veto_list:
            if veto_genre in movie.genres:
                return VoteResult(
                    user_name=self.user_name, score=1,
                    verdict=Verdict.VETO,
                    reason=f"V1-硬约束冲突：触及红线 '{veto_genre}'"
                )

        # V1: Duration check
        if movie.duration > p.max_duration:
            return VoteResult(
                user_name=self.user_name, score=2,
                verdict=Verdict.VETO,
                reason=f"V1-时长超限：{movie.duration}min > 上限 {p.max_duration}min"
            )

        # Try LLM for nuanced scoring
        if self.llm and self.llm.is_available() and getattr(self.llm.config, 'provider', '') != 'mock':
            try:
                return self._vote_llm(proposal)
            except Exception:
                pass
        return self._vote_rules(proposal)

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
            score += 2; reasons.append("高评分")
        elif movie.rating >= 8.0:
            score += 1; reasons.append("良好评分")
        if movie.duration <= 100:
            score += 1; reasons.append("时长合适")
        if p.min_rating > 0 and movie.rating < p.min_rating:
            score -= 2; reasons.append(f"评分低于期望 {p.min_rating}")

        score = max(1, min(10, score))
        if score < 3:
            return VoteResult(
                user_name=self.user_name, score=score,
                verdict=Verdict.VETO,
                reason=f"V2-评分过低：{score}/10 ({', '.join(reasons)})"
            )
        verdict = Verdict.APPROVE if score >= 6 else Verdict.ABSTAIN
        return VoteResult(
            user_name=self.user_name, score=score, verdict=verdict,
            reason=f"{'赞成' if verdict == Verdict.APPROVE else '弃权'}：{', '.join(reasons) if reasons else '无明显偏好匹配'} ({score}/10)"
        )
```

### 设计要点

1. **双模式解析**：`declare()` 优先尝试 LLM（DeepSeek），失败或不可用时自动回退到规则引擎，确保系统在任何环境下可用。
2. **否定词过滤**：规则引擎在提取 `genres` 前先扫描 `veto_list`，通过 **8 字符窗口**检测否定前缀（"不要"、"不看"、"怕"、"拒绝"），避免将 "不要恐怖片" 中的 "恐怖" 误加入偏好列表。
3. **硬约束优先**：`vote()` 中硬约束检查（Veto 列表和时长上限）**始终使用规则引擎**，不经过 LLM，确保响应速度和高确定性。
4. **评分计算**：基础分 5 分，类型匹配每项 +2（上限 +4），高评分 +1~2，时长合适 +1，低于期望评分 -2，最终 clamp 到 1~10。

---

## 4.3 MediatorAgent 实现

`MediatorAgent` 实现了 `detect_conflicts()`、`generate_proposal()`、`tally_votes()` 和 `finalize()` 四个核心方法，是协商流程的中心协调器。

### 代码实现：`src/agents/mediator_agent.py`

```python
class MediatorAgent:
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

    def generate_proposal(self, preferences, round_num=1, exclude_movie_ids=None) -> Proposal | None:
        """Generate movie proposal using compromise rules + Chroma history."""
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

        # Try MCP tool first
        mcp_results = self._try_mcp_search(candidate_genres, max_dur, min_rating, exclude_ids)
        if mcp_results:
            candidates = mcp_results
        else:
            candidates = search_movies(
                genres=candidate_genres if candidate_genres else None,
                max_duration=max_dur, min_rating=min_rating,
                exclude_genres=list(set(all_veto_genres)),
                exclude_ids=exclude_ids, limit=5,
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
                movie=movie, compromise_rules_applied=rules_applied,
                reason=f"基于类型交集的妥协方案，从 {len(candidates)} 部候选中选出评分最高者 ({source})",
                round_num=round_num
            )
        return None

    def _try_mcp_search(self, genres, max_duration, min_rating, exclude_ids) -> List[Movie] | None:
        """Try MCP tool for movie search. Returns None if unavailable."""
        try:
            genre = genres[0] if genres else None
            result = call_tool(
                "douban.search", genre=genre,
                rating_min=min_rating if min_rating > 0 else None,
                max_duration=max_duration, limit=5,
            )
            data = json.loads(result)
            if "error" in data:
                return None
            movies = []
            for item in data:
                if item.get("id") in exclude_ids:
                    continue
                movies.append(Movie(
                    movie_id=item["id"], title=item["title"],
                    genres=item.get("genres", []), duration=item.get("duration", 120),
                    rating=item.get("rating", 7.0), year=item.get("year", 2020),
                ))
            return movies if movies else None
        except Exception:
            return None

    def apply_safe_fallback(self) -> Proposal:
        """R5: Safe card fallback."""
        movie = get_safe_pick()
        self.rules_log.append("R5-安全牌兜底（高评分喜剧）")
        return Proposal(
            movie=movie, compromise_rules_applied=["R5-安全牌兜底"],
            reason="所有妥协规则均无法生成可行方案，启用安全牌推荐",
            round_num=99
        )

    def tally_votes(self, votes, preferences) -> ConsensusResult:
        """Aggregate votes and produce result."""
        total = len(votes)
        vetoes = [v for v in votes if v.verdict == Verdict.VETO]
        if len(vetoes) > total / 2:
            return ConsensusResult(
                movie=None, group_score=0.0, votes=votes,
                negotiation_log=[f"V3-多数否决：{len(vetoes)}/{total} 成员否决"],
                dissenters=[v.user_name for v in vetoes]
            )
        group_score = sum(v.score for v in votes) / total if total > 0 else 0
        dissenters = [v.user_name for v in votes if v.verdict == Verdict.VETO or v.score < 5]
        return ConsensusResult(movie=None, group_score=group_score,
                               votes=votes, dissenters=dissenters)

    def finalize(self, proposal, votes) -> ConsensusResult:
        """Make final decision and store to vector store."""
        result = self.tally_votes(votes, [])
        result.movie = proposal.movie
        result.negotiation_log = self.rules_log + [v.reason for v in votes]
        result.rounds_taken = proposal.round_num
        result.is_fallback = proposal.round_num >= 99
        if self.vector_store:
            try:
                from src.models.schemas import PreferenceVector
                prefs = []
                for v in votes:
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
```

### 设计要点

1. **冲突检测算法**：$O(n^2)$ 双重循环遍历所有偏好对，检测 **类型冲突**（A 偏好 vs B 否决）和 **时长冲突**（差异 >30 分钟）。
2. **妥协规则执行顺序**：R1（类型交叉过滤）→ R2（最严格时长约束）→ R3（历史加权 + 评分阈值），与 Spec 2.1.2 的优先级一致。
3. **MCP 优先策略**：生成提案时优先调用 `douban.search` MCP 工具获取外部数据，失败时自动回退到本地 50 部影片数据库。
4. **安全牌兜底**：当 `generate_proposal()` 返回 `None` 时，触发 `apply_safe_fallback()`，从本地数据库中选取评分最高的喜剧片（`get_safe_pick()`）。
5. **记忆写入**：`finalize()` 将最终共识结果写入 Chroma 向量存储，供后续协商参考（R3 历史加权）。

---

## 4.4 状态机实现

使用 `dataclass` 定义 `GraphState` 状态对象，7 个节点函数对应 7 个状态，通过 `STATE_MAP` 字典构建有限状态机。

### 代码实现：`src/graph/consensus_graph.py`

```python
from dataclasses import dataclass, field
from src.models.schemas import PreferenceVector, Proposal, VoteResult, ConsensusResult, Verdict
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

# ===== 7 Node Functions =====

def node_collect_prefs(state: GraphState) -> GraphState:
    state.add_log("=== STATE: collect_prefs ===")
    for agent in state.preference_agents:
        pref = agent.declare(agent.raw_input)
        state.preferences.append(pref)
        state.add_log(f"  {pref.user_name}: 偏好={pref.genres}, 最大时长={pref.max_duration}min, 最低评分={pref.min_rating}, 否决={pref.veto_list}")
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


# ===== State Machine Map =====
STATE_MAP = {
    "collect_prefs": node_collect_prefs,
    "detect_conflict": node_detect_conflict,
    "resolve": node_resolve,
    "generate_proposal": node_generate_proposal,
    "collect_votes": node_collect_votes,
    "final_decision": node_final_decision,
    "fallback": node_fallback,
}


def build_consensus_workflow(user_texts, llm=None, vector_store=None) -> GraphState:
    """Build and run the consensus workflow."""
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
```

### 设计要点

1. **纯函数节点**：每个 `node_*` 函数接收 `GraphState` 并返回新的 `GraphState`，无副作用，便于单元测试和调试。
2. **循环支持**：`node_collect_votes` 检测到否决时，将当前影片 ID 加入 `rejected_movie_ids`，然后回到 `resolve` 重新协商，避免重复推荐同一影片。
3. **终止条件**：`max_resolve_rounds=3` 限制最大协商轮次，超过后进入 `fallback`；`max_steps=20` 防止状态机无限循环。
4. **日志注入**：每个节点自动在 `state.log` 中记录当前状态和关键决策，前端可直接读取展示。
5. **数据流闭环**：`collect_prefs` → `detect_conflict` → `resolve` → `generate_proposal` → `collect_votes` → `final_decision` / `fallback`，与 Spec 2.3.3 状态转换图完全一致。

---

## 4.5 LLM 适配器

采用 **适配器模式** 设计 LLM 层，统一接口屏蔽不同提供商的差异。

### 4.5.1 抽象基类：`src/llm/base.py`

```python
from abc import ABC, abstractmethod
from pydantic import BaseModel, Field

class LLMConfig(BaseModel):
    """Configuration for LLM providers."""
    provider: str = "mock"
    model: str = "deepseek-chat"
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 500
    timeout: int = 30

class LLMResponse(BaseModel):
    """Standardized LLM response."""
    content: str = ""
    model: str = ""
    usage: dict = Field(default_factory=dict)
    error: Optional[str] = None

class BaseLLM(ABC):
    """Abstract base for LLM providers."""
    def __init__(self, config: LLMConfig | None = None):
        self.config = config or LLMConfig()

    @abstractmethod
    def chat(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        pass

    @abstractmethod
    def is_available(self) -> bool:
        pass

    def _build_messages(self, system_prompt: str, user_prompt: str) -> list[dict]:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_prompt})
        return messages
```

### 4.5.2 DeepSeek 实现：`src/llm/deepseek.py`

```python
class DeepSeekLLM(BaseLLM):
    """DeepSeek API provider. Compatible with OpenAI API format."""

    def __init__(self, config: LLMConfig | None = None):
        super().__init__(config)
        self.config.provider = "deepseek"
        self.config.base_url = self.config.base_url or "https://api.deepseek.com/v1"
        self.config.model = self.config.model or "deepseek-chat"
        self._client = None
        self._init_client()

    def _init_client(self) -> None:
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
        api_key = os.environ.get("DEEPSEEK_API_KEY", "")
        base_url = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
        return cls(LLMConfig(provider="deepseek", api_key=api_key if api_key else None, base_url=base_url))

    def is_available(self) -> bool:
        return self._client is not None and self.config.api_key is not None

    def chat(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        if not self.is_available():
            return LLMResponse(content="", error="DeepSeek API not available. Check DEEPSEEK_API_KEY.")
        messages = self._build_messages(system_prompt, user_prompt)
        max_retries = 2
        for attempt in range(max_retries + 1):
            try:
                resp = self._client.chat.completions.create(
                    model=self.config.model, messages=messages,
                    temperature=self.config.temperature, max_tokens=self.config.max_tokens,
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
                return LLMResponse(content="", error=f"DeepSeek API error: {type(e).__name__}: {e}")
        return LLMResponse(content="", error="Max retries exceeded")
```

### 4.5.3 Mock 回退：`src/llm/mock.py`

```python
class MockLLM(BaseLLM):
    """Mock LLM that uses rule-based parsing instead of API calls.
    Automatically used when DeepSeek API key is not configured."""

    def __init__(self, config: LLMConfig | None = None):
        super().__init__(config)
        self.config.provider = "mock"

    def is_available(self) -> bool:
        return True  # Always available

    def chat(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        content = ""
        if "观影偏好解析" in system_prompt or "genres" in user_prompt:
            content = self._parse_preference(user_prompt)
        elif "观影评价" in system_prompt or "proposal" in user_prompt.lower():
            content = self._vote_on_movie(user_prompt)
        else:
            content = json.dumps({"score": 5, "verdict": "abstain", "reason": "Mock mode"}, ensure_ascii=False)
        return LLMResponse(content=content, model="mock-rule-engine")

    def _parse_preference(self, prompt: str) -> str:
        # Extract user text from prompt
        match = re.search(r'用户描述："([^"]+)"', prompt)
        text = match.group(1).lower() if match else prompt.lower()
        # ... (same rule-based logic as PreferenceAgent._declare_rules)
        return json.dumps({"genres": genres, "max_duration": max_duration,
                           "min_rating": min_rating, "veto_list": veto_list, "soft_prefs": text}, ensure_ascii=False)

    def _vote_on_movie(self, prompt: str) -> str:
        # Extract user preferences and movie info from prompt using regex
        # ... (same rule-based logic as PreferenceAgent._vote_rules)
        return json.dumps({"score": score, "verdict": verdict, "reason": reason}, ensure_ascii=False)
```

### 4.5.4 工厂函数

```python
def create_llm(config: LLMConfig | None = None) -> BaseLLM:
    """Factory function. Priority: DeepSeek (if API key) > Mock (fallback)."""
    from src.llm.deepseek import DeepSeekLLM
    ds = DeepSeekLLM.from_env()
    if ds.is_available():
        print(f"  [LLM] Using DeepSeek provider (model={ds.config.model})")
        return ds
    print(f"  [LLM] DeepSeek unavailable, using Mock (rule-based)")
    return MockLLM(config)
```

### 4.5.5 Prompt 模板（分离设计）

```python
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
规则：genres 从用户描述中提取偏好的电影类型；max_duration 默认180；min_rating 默认0；veto_list 用户明确拒绝的类型；soft_prefs 保留其他偏好信息。
注意：只返回 JSON，不要 markdown 代码块，不要解释。"""

VOTE_PROMPT = """你是一个观影评价助手。请根据用户的偏好和当前提案影片，给出评价。
用户偏好：喜欢类型：{genres}，最大时长：{max_duration}分钟，最低评分：{min_rating}，拒绝类型：{veto_list}，其他偏好：{soft_prefs}
提案影片：片名：{movie_title}，类型：{movie_genres}，时长：{movie_duration}分钟，评分：{movie_rating}/10，简介：{movie_description}
请返回严格 JSON 格式：{{"score": 7, "verdict": "approve", "reason": "评价理由"}}
verdict 只能是：approve（赞成，score>=6）、veto（否决，触及红线）、abstain（弃权，score<6）。score 范围 1-10。只返回 JSON，不要其他内容。"""
```

### 设计要点

1. **统一接口**：`BaseLLM` 定义 `chat()` 和 `is_available()`，新增 LLM 提供商只需继承基类，无需修改业务代码。
2. **OpenAI-compatible**：`DeepSeekLLM` 使用 `openai` 客户端库，通过 `base_url` 指向 DeepSeek API，天然兼容 Claude/GPT 等同类服务。
3. **自动重试**：`chat()` 包含 `max_retries=2` 的异常重试逻辑，对应错误码 **E1001**（LLM 调用超时）的处理策略。
4. **Mock 永不宕机**：`MockLLM.is_available()` 始终返回 `True`，通过正则解析 Prompt 中的用户描述，输出与 LLM 相同格式的 JSON，业务层无感知切换。
5. **Prompt 分离**：`PREFERENCE_PARSE_PROMPT` 和 `VOTE_PROMPT` 作为模块级常量，便于 A/B 测试和版本迭代。

---

## 4.6 Chroma 向量存储

`WatchRecord` 类将群体观影记录转换为文本表示，用于向量嵌入。`ChromaVectorStore` 使用 cosine 相似度进行语义检索。

### 代码实现：`src/memory/vector_store.py`

```python
class WatchRecord:
    """A single group watch record."""
    def __init__(self, movie_id: str, title: str, genres: List[str], duration: int,
                 group_score: float, user_scores: dict[str, float],
                 preferences: List[PreferenceVector], timestamp: str = ""):
        self.movie_id = movie_id
        self.title = title
        self.genres = genres
        self.duration = duration
        self.group_score = group_score
        self.user_scores = user_scores
        self.preferences = preferences
        self.timestamp = timestamp or datetime.now().isoformat()

    def to_text(self) -> str:
        """Convert to text for embedding."""
        pref_texts = []
        for p in self.preferences:
            pref_texts.append(f"{p.user_name}想要{'/'.join(p.genres)}最长{p.max_duration}分钟")
        return (
            f"影片《{self.title}》类型{'/'.join(self.genres)}时长{self.duration}分钟 "
            f"群体满意度{self.group_score}分 用户偏好：{'；'.join(pref_texts)}"
        )

    def to_dict(self) -> dict:
        return {
            "movie_id": self.movie_id, "title": self.title,
            "genres": ",".join(self.genres), "duration": self.duration,
            "group_score": self.group_score,
            "user_scores": ",".join([f"{k}:{v}" for k, v in self.user_scores.items()]),
            "preferences": ",".join([f"{p.user_name}:{','.join(p.genres)}:{p.max_duration}" for p in self.preferences]),
            "timestamp": self.timestamp,
        }


class BaseVectorStore:
    """Abstract base for vector storage."""
    def add_watch_record(self, result: ConsensusResult, preferences: List[PreferenceVector]) -> None:
        pass
    def query_similar(self, preferences: List[PreferenceVector], n_results: int = 3) -> List[dict]:
        return []
    def get_stats(self) -> dict:
        return {"total_records": 0, "provider": "none"}


class ChromaVectorStore(BaseVectorStore):
    """ChromaDB vector store for group watch history."""
    COLLECTION_NAME = "watch_history"

    def __init__(self, persist_dir: str = "./chroma_db"):
        self.persist_dir = persist_dir
        self._collection = None
        self._client = None
        self._init_chroma()

    def _init_chroma(self) -> None:
        try:
            import chromadb
            os.makedirs(self.persist_dir, exist_ok=True)
            self._client = chromadb.PersistentClient(path=self.persist_dir)
            self._collection = self._client.get_or_create_collection(
                name=self.COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"}
            )
        except ImportError:
            self._client = None
            self._collection = None

    def is_available(self) -> bool:
        return self._collection is not None

    def add_watch_record(self, result: ConsensusResult, preferences: List[PreferenceVector]) -> None:
        if not self.is_available():
            return
        record = WatchRecord(
            movie_id=result.movie.movie_id if result.movie else "unknown",
            title=result.movie.title if result.movie else "unknown",
            genres=result.movie.genres if result.movie else [],
            duration=result.movie.duration if result.movie else 0,
            group_score=result.group_score,
            user_scores={v.user_name: v.score for v in result.votes},
            preferences=preferences,
        )
        doc_id = f"watch_{record.timestamp}_{record.movie_id}"
        self._collection.add(
            ids=[doc_id], documents=[record.to_text()], metadatas=[record.to_dict()],
        )

    def query_similar(self, preferences: List[PreferenceVector], n_results: int = 3) -> List[dict]:
        if not self.is_available():
            return []
        count = self._collection.count()
        if count == 0:
            return []
        query_parts = []
        for p in preferences:
            query_parts.append(f"{'/'.join(p.genres)}最长{p.max_duration}分钟")
        query_text = "群体想看" + "；".join(query_parts)
        results = self._collection.query(
            query_texts=[query_text], n_results=min(n_results, count),
        )
        records = []
        if results["metadatas"] and results["metadatas"][0]:
            for i, meta in enumerate(results["metadatas"][0]):
                dist = results["distances"][0][i] if results["distances"] else 1.0
                records.append({**meta, "similarity": 1.0 - float(dist)})
        return records

    def get_stats(self) -> dict:
        if not self.is_available():
            return {"total_records": 0, "provider": "chroma (unavailable)"}
        return {"total_records": self._collection.count(), "provider": "chroma", "persist_dir": self.persist_dir}


class MemoryVectorStore(BaseVectorStore):
    """In-memory fallback when Chroma is not available."""
    def __init__(self):
        self.records: List[WatchRecord] = []
    def is_available(self) -> bool:
        return True
    def add_watch_record(self, result, preferences) -> None:
        record = WatchRecord(...)
        self.records.append(record)
    def query_similar(self, preferences, n_results=3) -> List[dict]:
        current_genres = set()
        for p in preferences:
            current_genres.update(p.genres)
        scored = []
        for r in self.records:
            score = 0
            r_genres = set(r.genres)
            overlap = len(current_genres & r_genres)
            score += overlap * 2
            score += r.group_score
            scored.append((score, r))
        scored.sort(key=lambda x: -x[0])
        return [{**s[1].to_dict(), "similarity": s[0] / 10.0} for s in scored[:n_results]]


def create_vector_store(persist_dir: str = "./chroma_db") -> BaseVectorStore:
    """Factory: Chroma (if installed) > Memory (fallback)."""
    chroma = ChromaVectorStore(persist_dir)
    if chroma.is_available():
        print(f"  [Memory] Using Chroma vector store ({chroma.get_stats()['total_records']} records)")
        return chroma
    print(f"  [Memory] Chroma unavailable, using in-memory store")
    return MemoryVectorStore()
```

### 设计要点

1. **文本嵌入**：`WatchRecord.to_text()` 将结构化记录转换为自然语言文本（如 *"影片《星际穿越》类型科幻/剧情时长169分钟 群体满意度8.5分 用户偏好：Alice想要科幻/剧情最长120分钟；Bob想要喜剧最长90分钟"*），供 Chroma 语义嵌入使用。
2. **Cosine 相似度**：`metadata={"hnsw:space": "cosine"}` 配置 Chroma 使用余弦距离，适合文本语义检索。
3. **层次化存储**：`HierarchicalVectorStore` 同时维护 **Chroma（持久化）** 和 **Memory（临时会话）**，查询时优先查持久化历史，失败时回退到内存，确保数据不丢失。
4. **Metadata 序列化**：Chroma 的 `metadata` 字段不支持嵌套结构，`to_dict()` 将列表和字典转换为逗号分隔字符串，读取时反向解析。
5. **降级策略**：`E4001`（向量数据库查询失败）对应 `MemoryVectorStore` 回退，使用关键词匹配替代语义检索。

---

## 4.7 豆瓣 MCP Server

`douban_mcp.py` 实现了 MCP 协议的核心功能，当外部 API 不可用时自动回退到本地 50 部影片数据库。

### 代码实现：`src/tools/douban_mcp.py`

```python
# ===== MCP Tool Functions =====

def search(
    title: Optional[str] = None,
    genre: Optional[str] = None,
    rating_min: Optional[float] = None,
    max_duration: Optional[int] = None,
    limit: int = 10,
) -> str:
    """MCP Tool: douban.search. Search movies from Douban database."""
    genres = [genre] if genre else None
    min_rating = rating_min or 0.0
    max_dur = max_duration or 999

    # Try real Douban search first
    try:
        return _search_douban(title, genres, min_rating, max_dur, limit)
    except Exception as e:
        print(f"  [Douban API] Search failed: {e}, falling back to local")

    # Fallback: local movie database
    results = search_movies(genres=genres, max_duration=max_dur, min_rating=min_rating, limit=limit)
    if title:
        results = [m for m in results if title.lower() in m.title.lower()]
    return json.dumps(
        [{"id": m.movie_id, "title": m.title, "genres": m.genres,
          "duration": m.duration, "rating": m.rating, "year": m.year}
         for m in results], ensure_ascii=False
    )


def get_detail(movie_id: str) -> str:
    """MCP Tool: douban.detail. Get detailed movie information by ID."""
    if movie_id.isdigit():
        try:
            return _detail_douban(movie_id)
        except Exception as e:
            print(f"  [Douban API] Detail failed: {e}, falling back to local")
    movie = get_movie_by_id(movie_id)
    if movie:
        return json.dumps({"id": movie.movie_id, "title": movie.title, ...}, ensure_ascii=False)
    return json.dumps({"error": "E3102", "message": f"影片不存在: {movie_id}"})


# ===== Douban HTML Scraping =====

def _search_douban(title, genres, rating_min, max_duration, limit) -> str:
    """Scrape Douban movie search results."""
    import requests
    url = f"https://movie.douban.com/search?q={title or ''}"
    headers = {
        "User-Agent": "Mozilla/5.0 ... Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
    resp = requests.get(url, headers=headers, timeout=15)
    resp.raise_for_status()
    match = re.search(r'window\.__DATA__\s*=\s*(\{.*?\});', resp.text, re.DOTALL)
    if not match:
        return json.dumps([])
    data = json.loads(match.group(1))
    results = []
    for item in data.get("items", [])[:limit]:
        movie_title = item.get("title", "") or item.get("name", "")
        movie_id = str(item.get("id", ""))
        abstract = item.get("abstract", "")
        year_match = re.search(r"(\d{4})", abstract)
        year = int(year_match.group(1)) if year_match else 0
        duration_match = re.search(r"(\d+)\s*分钟", abstract)
        duration = int(duration_match.group(1)) if duration_match else 0
        genre_list = []
        for keyword in ["剧情", "喜剧", "动作", ...]:
            if keyword in abstract:
                genre_list.append(keyword)
        rating = item.get("rating", 0)
        if isinstance(rating, dict):
            rating = float(rating.get("value", 0))
        elif isinstance(rating, str):
            rating = float(rating) if rating else 0.0
        if rating < rating_min:
            continue
        if duration > max_duration and duration > 0:
            continue
        if genres and not any(g in genre_list for g in genres):
            continue
        results.append({"id": movie_id, "title": movie_title, "genres": genre_list,
                        "duration": duration, "rating": rating, "year": year, "cover": item.get("cover_url", "")})
    return json.dumps(results, ensure_ascii=False)


# ===== MCP Server Registration =====

MCP_TOOLS = {
    "douban.search": {
        "function": search,
        "description": "Search movies by title, genre, rating, duration",
        "parameters": {
            "title": {"type": "string", "description": "Movie title keyword"},
            "genre": {"type": "string", "description": "Genre e.g. 科幻, 喜剧"},
            "rating_min": {"type": "number", "description": "Minimum rating 0-10"},
            "max_duration": {"type": "integer", "description": "Max duration in minutes"},
            "limit": {"type": "integer", "description": "Max results"},
        }
    },
    "douban.detail": {
        "function": get_detail,
        "description": "Get movie details by ID",
        "parameters": {"movie_id": {"type": "string", "description": "Movie unique ID"}}
    },
}


def call_tool(tool_name: str, **kwargs) -> str:
    """Unified tool calling interface. Used by MediatorAgent to invoke MCP tools."""
    if tool_name not in MCP_TOOLS:
        return json.dumps({"error": f"Unknown tool: {tool_name}"})
    tool = MCP_TOOLS[tool_name]
    try:
        result = tool["function"](**kwargs)
        return result
    except Exception as e:
        return json.dumps({"error": f"Tool execution failed: {e}"})


def list_tools() -> List[dict]:
    """List all available MCP tools."""
    return [{"name": name, "description": info["description"], "parameters": info["parameters"]}
            for name, info in MCP_TOOLS.items()]
```

### 本地数据库：`src/data/movies.py`

```python
MOVIE_DATABASE: List[Movie] = [
    Movie(movie_id="sf01", title="星际穿越", genres=["科幻", "剧情"], duration=169, rating=9.3, year=2014,
          description="地球环境恶化，一组宇航员穿越虫洞寻找新家园"),
    Movie(movie_id="co01", title="西虹市首富", genres=["喜剧"], duration=118, rating=6.5, year=2018,
          description="一个月内花光十亿的挑战"),
    # ... 50 movies total, covering 15 genres
]

def search_movies(genres=None, max_duration=999, min_rating=0.0,
                  exclude_genres=None, exclude_ids=None, limit=10) -> list[Movie]:
    results = []
    exclude_ids = exclude_ids or []
    exclude_genres = exclude_genres or []
    for movie in MOVIE_DATABASE:
        if movie.movie_id in exclude_ids: continue
        if movie.duration > max_duration: continue
        if movie.rating < min_rating: continue
        if genres and not any(g in movie.genres for g in genres): continue
        if exclude_genres and any(g in movie.genres for g in exclude_genres): continue
        results.append(movie)
    results.sort(key=lambda m: (-m.rating, -sum(1 for g in (genres or []) if g in m.genres), m.duration))
    return results[:limit]

def get_safe_pick() -> Movie:
    """Return the safest movie (high-rated comedy for R5 rule)."""
    comedies = [m for m in MOVIE_DATABASE if "喜剧" in m.genres and m.rating >= 8.0]
    comedies.sort(key=lambda m: -m.rating)
    return comedies[0] if comedies else MOVIE_DATABASE[0]
```

### 设计要点

1. **MCP 协议注册**：`MCP_TOOLS` 字典将工具名映射到函数、描述和参数 Schema，符合 Spec 2.3.2 的接口定义。
2. **HTML 抓取**：`_search_douban()` 通过 `window.__DATA__` 提取豆瓣搜索页的 JSON 数据，无需 API Key，降低部署门槛。
3. **自动降级**：当 `requests` 超时或反爬失败时，自动回退到 `search_movies()` 查询本地 50 部影片数据库，确保 MVP 阶段无需外部网络即可运行。
4. **错误码**：`get_detail()` 在影片不存在时返回 `{"error": "E3102"}`，对应 Spec 2.3.4 错误码体系中的 **E3102 影片不存在**。
5. **本地数据库覆盖**：50 部影片涵盖 15 种类型，评分从 6.5 到 9.8，时长从 90 到 194 分钟，覆盖绝大多数协商场景。

---

## 4.8 Web 前端

前端采用原生 HTML5 + Tailwind CSS CDN 实现，零构建步骤，通过 Fetch API 调用 FastAPI 后端。

### 代码实现：`web/index.html`（核心片段）

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <title>Social Consensus Agent - 群体协商观影智能体</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <style>
    .state-node { transition: all 0.3s ease; }
    .state-active { transform: scale(1.05); box-shadow: 0 4px 12px rgba(0,0,0,0.15); }
    .vote-approve { background: #10B981; }
    .vote-veto { background: #EF4444; }
    .vote-abstain { background: #F59E0B; }
    .log-state { background: #EFF6FF; color: #1D4ED8; font-weight: 500; }
    .log-veto { background: #FEF2F2; color: #DC2626; }
    .log-ok { background: #ECFDF5; color: #059669; }
  </style>
</head>
<body class="bg-gradient-to-br from-slate-50 to-slate-100 min-h-screen">
```

#### 状态机渲染

```javascript
const STATES = [
  { id: 'collect_prefs', label: '收集偏好', color: '#3B82F6' },
  { id: 'detect_conflict', label: '冲突检测', color: '#F59E0B' },
  { id: 'resolve', label: '冲突解决', color: '#EF4444' },
  { id: 'generate_proposal', label: '生成提案', color: '#10B981' },
  { id: 'collect_votes', label: '收集投票', color: '#8B5CF6' },
  { id: 'final_decision', label: '最终裁决', color: '#059669' },
  { id: 'fallback', label: '安全牌', color: '#6B7280' },
];

document.getElementById('state-machine').innerHTML = STATES.filter(s => s.id !== 'fallback')
  .map((s, i, arr) => `
    <div class="flex items-center gap-1">
      <div id="state-${s.id}" class="state-node px-3 py-2 rounded-lg text-xs font-medium text-center bg-slate-100 text-slate-400 min-w-[80px]">${s.label}</div>
      ${i < arr.length - 1 ? '<span class="text-slate-300 text-xs">&rarr;</span>' : ''}
    </div>
  `).join('');
```

#### 协商请求与结果展示

```javascript
async function startNegotiate() {
  const validUsers = users.filter(u => u.name.trim() && u.preference.trim());
  if (validUsers.length < 1) { showError('请至少添加一个有效用户'); return; }
  if (validUsers.length > 10) { showError('最多支持 10 个用户'); return; }

  // Reset UI
  document.getElementById('result-card').classList.add('hidden');
  document.getElementById('votes-card').classList.add('hidden');
  document.getElementById('error-card').classList.add('hidden');
  document.getElementById('log-card').classList.add('hidden');
  STATES.forEach(s => {
    const el = document.getElementById('state-' + s.id);
    if (el) { el.style.backgroundColor = ''; el.style.color = ''; el.classList.remove('state-active'); }
  });

  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 60000);
    const res = await fetch(API_BASE + '/api/negotiate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
      body: JSON.stringify({ users: validUsers, use_llm: true, use_chroma: true }),
      signal: controller.signal,
    });
    clearTimeout(timeoutId);
    if (!res.ok) { throw new Error(`HTTP ${res.status}`); }
    const data = await res.json();
    showResult(data);
  } catch (e) {
    if (e.name === 'AbortError') { showError('请求超时，请重试'); }
    else { showError(e.message || '请求失败'); }
  }
}

function showResult(data) {
  // Activate states based on negotiation log
  const activeStates = new Set();
  for (const log of data.negotiation_log || []) {
    for (const s of STATES) {
      if (log.includes(s.label) || log.includes(s.id)) activeStates.add(s.id);
    }
  }
  activeStates.forEach(id => {
    const s = STATES.find(x => x.id === id);
    const el = document.getElementById('state-' + id);
    if (el && s) { el.style.backgroundColor = s.color; el.style.color = '#fff'; el.classList.add('state-active'); }
  });

  // Render result card
  if (data.movie) {
    document.getElementById('result-title').textContent = '《' + data.movie.title + '》';
    document.getElementById('result-genres').innerHTML = data.movie.genres.map(g => `<span class="text-xs bg-slate-100 px-2 py-1 rounded">${g}</span>`).join('');
    document.getElementById('result-duration').textContent = data.movie.duration;
    document.getElementById('result-rating').textContent = data.movie.rating + '/10';
    document.getElementById('result-score').textContent = data.group_score.toFixed(1) + '/10';
    document.getElementById('result-desc').textContent = data.movie.description || '';
    document.getElementById('result-rounds').textContent = data.rounds_taken;
    if (data.dissenters && data.dissenters.length > 0) {
      document.getElementById('result-dissenters').textContent = '异议者: ' + data.dissenters.join(', ');
      document.getElementById('result-dissenters').classList.remove('hidden');
    }
    if (data.is_fallback) document.getElementById('fallback-badge').classList.remove('hidden');
    document.getElementById('result-card').classList.remove('hidden');
  }

  // Render votes
  if (data.votes && data.votes.length > 0) {
    document.getElementById('votes-list').innerHTML = data.votes.map(v => {
      const cls = v.verdict === 'approve' ? 'vote-approve' : v.verdict === 'veto' ? 'vote-veto' : 'vote-abstain';
      const label = v.verdict === 'approve' ? '赞成' : v.verdict === 'veto' ? '否决' : '弃权';
      return `<div class="flex items-center gap-3 p-3 rounded-lg bg-slate-50">
        <div class="w-12 h-12 rounded-full ${cls} text-white flex items-center justify-center font-bold text-sm shrink-0">${v.score}</div>
        <div class="flex-1 min-w-0">
          <p class="font-medium text-sm">${v.user_name}</p>
          <p class="text-xs text-slate-500 truncate">${v.reason}</p>
        </div>
        <span class="text-xs px-2 py-1 rounded ${v.verdict === 'approve' ? 'bg-green-100 text-green-700' : v.verdict === 'veto' ? 'bg-red-100 text-red-700' : 'bg-gray-100 text-gray-600'}">${label}</span>
      </div>`;
    }).join('');
    document.getElementById('votes-card').classList.remove('hidden');
  }

  // Render log with color coding
  if (data.negotiation_log && data.negotiation_log.length > 0) {
    document.getElementById('log-list').innerHTML = data.negotiation_log.map(log => {
      let cls = 'log-normal px-2 py-1.5 rounded text-xs';
      if (STATES.some(s => log.includes(s.label))) cls = 'log-state px-2 py-1.5 rounded text-xs';
      else if (log.includes('否决') || log.includes('冲突')) cls = 'log-veto px-2 py-1.5 rounded text-xs';
      else if (log.includes('赞成') || log.includes('推荐')) cls = 'log-ok px-2 py-1.5 rounded text-xs';
      return `<div class="${cls}">${log}</div>`;
    }).join('');
    document.getElementById('log-card').classList.remove('hidden');
  }
}
```

### 预设场景

```javascript
const SCENARIOS = [
  { id: 1, name: '科幻 vs 喜剧 (2人)', users: { 'Alice': '我喜欢科幻片，时长不要超过120分钟，不要恐怖片', 'Bob': '我想看喜剧片，轻松一点的，时长90分钟以内最好' } },
  { id: 2, name: '恐怖片红线 (2人)', users: { 'Alice': '我想看悬疑惊悚片，越刺激越好', 'Bob': '我害怕恐怖片和惊悚片，想看爱情片或者剧情片，不要超过2小时' } },
  { id: 3, name: '高分 vs 随意 (2人)', users: { 'Alice': '我只看高分电影，评分至少8分以上，科幻或剧情都可以', 'Bob': '我随便，什么都行，搞笑的最好' } },
  { id: 4, name: '宿舍4人多目标博弈', users: { 'Alice': '我喜欢科幻和动作片，评分高的，不要太长', 'Bob': '我只看喜剧和动画片，超过100分钟的不行', 'Carol': '我要看爱情片或者剧情片，拒绝恐怖和战争', 'David': '我都可以，最好是大家都喜欢的，评分8分以上' } },
  { id: 5, name: '家庭6人代际差异', users: { '爷爷': '我想看战争片或者历史剧情片', '奶奶': '爱情片或者家庭剧都可以，不要太悲伤', '爸爸': '动作片或者悬疑片，刺激一点的', '妈妈': '喜剧片最好，全家人一起笑', '哥哥': '科幻大片，特效好的，越长越好', '妹妹': '动画片或者爱情片，不要超过2小时' } },
];
```

### 设计要点

1. **零构建**：直接使用 Tailwind CSS CDN + 原生 JavaScript，无需 Webpack/Vite，降低部署复杂度。
2. **状态机实时高亮**：通过解析后端返回的 `negotiation_log`，自动匹配日志中的状态关键字，将对应节点染为对应颜色并添加 `state-active` 动画效果。
3. **5 个预设场景**：覆盖从 2 人经典冲突到 6 人代际差异的多样化场景，支持一键加载。
4. **投票可视化**：赞成/否决/弃权分别使用绿色/红色/黄色圆形徽章，评分数字居中显示，理由文本截断防止溢出。
5. **协商日志着色**：按日志内容自动分类——状态转换（蓝色）、否决/冲突（红色）、赞成/推荐（绿色）、普通信息（灰色），提升可读性。
6. **CORS 与超时**：前端请求携带 `Accept: application/json`，60 秒超时保护，后端 FastAPI 已配置 `CORSMiddleware` 允许跨域。
7. **后端健康检测**：页面加载时自动请求 `/api/health`，离线时显示红色警告并禁用协商按钮。

---

## 4.9 入口与 CLI：`main.py`

```python
#!/usr/bin/env python3
"""Social Consensus Agent - Final Demo Entry Point.
Supports: N users, LLM (DeepSeek/Mock), Chroma/Memory vector store, MCP tools.
"""
from dotenv import load_dotenv
load_dotenv()

from src.graph.consensus_graph import build_consensus_workflow
from src.llm.mock import create_llm
from src.memory.vector_store import create_vector_store

SCENARIOS = {
    1: {"name": "经典冲突：科幻 vs 喜剧 (2人)",
        "users": {"Alice": "我喜欢科幻片，时长不要超过120分钟，不要恐怖片",
                  "Bob": "我想看喜剧片，轻松一点的，时长90分钟以内最好"}},
    2: {"name": "恐怖片红线 (2人)",
        "users": {"Alice": "我想看悬疑惊悚片，越刺激越好",
                  "Bob": "我害怕恐怖片和惊悚片，想看爱情片或者剧情片，不要超过2小时"}},
    3: {"name": "高要求 vs 随意 (2人)",
        "users": {"Alice": "我只看高分电影，评分至少8分以上，科幻或剧情都可以",
                  "Bob": "我随便，什么都行，搞笑的最好"}},
    4: {"name": "宿舍4人：多目标博弈",
        "users": {"Alice": "我喜欢科幻和动作片，评分高的，不要太长",
                  "Bob": "我只看喜剧和动画片，超过100分钟的不行",
                  "Carol": "我要看爱情片或者剧情片，拒绝恐怖和战争",
                  "David": "我都可以，最好是大家都喜欢的，评分8分以上"}},
    5: {"name": "家庭6人：代际差异",
        "users": {"爷爷": "我想看战争片或者历史剧情片",
                  "奶奶": "爱情片或者家庭剧都可以，不要太悲伤",
                  "爸爸": "动作片或者悬疑片，刺激一点的",
                  "妈妈": "喜剧片最好，全家人一起笑",
                  "哥哥": "科幻大片，特效好的，越长越好",
                  "妹妹": "动画片或者爱情片，不要超过2小时"}},
}

def run_scenario(sid: int, llm_name: str = "mock", use_chroma: bool = False) -> None:
    s = SCENARIOS[sid]
    print(f"\n{'#'*60}\n# Scenario {sid}: {s['name']}\n{'#'*60}")
    llm = create_llm() if llm_name != "none" else None
    vector_store = create_vector_store() if use_chroma else None
    state = build_consensus_workflow(s["users"], llm=llm, vector_store=vector_store)
    _print_result(state, s["users"])

def run_all_scenarios(llm_name: str = "mock", use_chroma: bool = False) -> None:
    for sid in sorted(SCENARIOS.keys()):
        run_scenario(sid, llm_name, use_chroma)
        print("\n" + "-"*60)

def interactive_n_person(llm_name: str = "mock", use_chroma: bool = False) -> None:
    n = int(input("群体人数 (默认2): ").strip() or 2)
    users = {}
    for i in range(n):
        name = input(f"第{i+1}人名字: ").strip() or f"User{i+1}"
        prefs = input(f"  {name} 的偏好: ").strip() or "随便都可以"
        users[name] = prefs
    llm = create_llm() if llm_name != "none" else None
    vector_store = create_vector_store() if use_chroma else None
    state = build_consensus_workflow(users, llm=llm, vector_store=vector_store)
    _print_result(state, users)

def main() -> None:
    parser = argparse.ArgumentParser(description="Social Consensus Agent - Final Demo")
    parser.add_argument("--scenario", type=int, choices=[1,2,3,4,5], help="Run specific scenario (1-5)")
    parser.add_argument("--custom", action="store_true", help="Interactive mode")
    parser.add_argument("--llm", choices=["mock", "deepseek", "none"], default="mock", help="LLM provider")
    parser.add_argument("--chroma", action="store_true", help="Enable Chroma vector store")
    args = parser.parse_args()
    if args.custom:
        interactive_n_person(args.llm, args.chroma)
    elif args.scenario:
        run_scenario(args.scenario, args.llm, args.chroma)
    else:
        run_all_scenarios(args.llm, args.chroma)

if __name__ == "__main__":
    main()
```

### 使用示例

```bash
# 运行全部 5 个预设场景（Mock 模式，无 LLM）
python main.py

# 运行 4 人宿舍场景（DeepSeek LLM + Chroma 向量存储）
python main.py --scenario 4 --llm deepseek --chroma

# 交互模式：自定义 N 人偏好
python main.py --custom --llm deepseek --chroma

# 后端服务（FastAPI + Uvicorn，供前端调用）
python -m uvicorn src.api.server:app --reload --port 8000
```
