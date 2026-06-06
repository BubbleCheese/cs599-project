# 三、API Spec（接口规格）

API Spec 定义 Agent 间通信接口、MCP 工具接口与状态转换接口的完整契约，包括输入参数、输出结构与错误码体系。面向角色：前后端开发工程师、测试工程师。

## 3.1 Agent 通信接口

Preference Agent 与 Mediator Agent 之间的核心通信接口（基于 Pydantic 模型）：

|**接口名**|**输入（Input）**|**输出（Output）**|
|-|-|-|
|PreferenceAgent.declare()|user\_text, hard\_rules\[], soft\_prefs\[]|PreferenceVector {genre, max\_duration, rating\_min, veto\_list}|
|PreferenceAgent.vote()|proposal: Proposal, history\[]|VoteResult {score(1-10), verdict, reason}|
|MediatorAgent.generate()|prefs\[], round: int|Proposal {movie\_id, title, genre, compromise\_log}|
|MediatorAgent.finalize()|votes\[], satisfaction: float|ConsensusResult {movie, group\_score, dissenters}|

## 3.2 MCP 工具接口

MCP Server 暴露的工具函数签名与返回值定义：

|**工具名**|**参数**|**返回**|**异常**|
|-|-|-|-|
|douban.search|title?, genre?, rating\_min?|List\[MovieMeta]|E3101 超时|
|douban.get\_detail|movie\_id: str|MovieDetail|E3102 影片不存在|
|imdb.search|title: str, lang?|List\[MovieMeta]|E3201 超时|
|calendar.check|duration\_min, date?|{available, reason?}|E3301 日期无效|

## 3.3 状态转换接口

LangGraph 状态机的节点函数签名与边条件定义：

|**状态节点**|**函数签名**|**出边条件**|**目标状态**|
|-|-|-|-|
|collect\_prefs|collect(state)|all\_declared == true|detect\_conflict|
|detect\_conflict|detect(state)|conflict == true|resolve|
|detect\_conflict|detect(state)|conflict == false|generate|
|resolve|resolve\_conflict(state)|resolved == true|generate|
|resolve|resolve\_conflict(state)|max\_rounds == true|fallback|
|generate|propose(state)|proposals > 0|collect\_votes|
|collect\_votes|tally(state)|all\_veto == false|final|
|collect\_votes|tally(state)|any\_veto == true|resolve|

## 3.4 错误码体系

系统统一错误码规范（所有接口遵循 E 级分类法）：

|**错误码**|**含义**|**处理策略**|
|-|-|-|
|E1001|LLM 调用超时|自动重试 2 次，仍失败则降级至本地模型|
|E1002|LLM 返回格式非法|丢弃当前结果，重新生成（附带 format 约束）|
|E2001|协商轮次超限|强制进入 fallback 状态，推荐安全牌|
|E2002|所有提案被否决|触发规则 R5（安全牌兜底）|
|E3001|MCP Server 不可用|标记离线，使用缓存数据或跳过该维度|
|E3002|MCP 返回数据为空|扩大查询条件重试，仍为空则返回 E2002|
|E4001|向量数据库查询失败|降级为内存模式，使用最近 10 条记录|

错误码分类规则：E1xxx = LLM 层错误，E2xxx = 协商层错误，E3xxx = 工具层错误，E4xxx = 存储层错误。

