# 二、Architecture Spec（架构规格）

Architecture Spec 定义系统的组件边界、接口矩阵、数据流与部署拓扑。面向角色：架构师、后端开发工程师、DevOps。

## 2.1 组件清单（Component Inventory）

系统由以下 8 个核心组件构成，每个组件包含独立的职责、依赖与生命周期：

|**组件 ID**|**组件名称**|**职责**|**依赖**|**生命周期**|
|-|-|-|-|-|
|C1|PreferenceAgent|偏好表达、利益维护、投票反馈|LLM|Session|
|C2|MediatorAgent|冲突检测、提案生成、最终裁决|LLM, C1|Session|
|C3|ConsensusGraph|LangGraph 状态机编排|C1, C2|Request|
|C4|CompromiseEngine|妥协规则计算引擎|C7|Request|
|C5|VectorStore|向量数据库（Chroma）|无|Singleton|
|C6|MCPManager|MCP Server 注册与路由|C7|Singleton|
|C7|MCP Server x3|豆瓣/IMDb/日历 API|外部 API|Singleton|
|C8|Logger|协商过程日志与 Trace|无|Singleton|

## 2.2 接口矩阵（Interface Matrix）

定义组件间的调用关系与数据契约（调用方向：Src -> Dst）：

|**Src**|**Dst**|**接口名**|**数据契约**|**调用方式**|
|-|-|-|-|-|
|C1|C2|declare()|PreferenceVector|Message|
|C2|C1|send\_proposal()|Proposal|Message|
|C1|C2|vote()|VoteResult|Message|
|C2|C4|resolve()|Conflict + Prefs|Function|
|C4|C7|search\_movies()|Query Params|MCP|
|C2|C5|query\_history()|PreferenceVector|Vector Search|
|C3|C8|log\_state()|State + Context|Async|

## 2.3 数据流规格（Data Flow Spec）

系统核心数据流分为三条主线：

* 偏好流：User -> PreferenceAgent（自然语言）-> 解析为 PreferenceVector（结构化）-> 通过 DECLARE 消息发送至 Mediator
* 提案流：Mediator -> 调用 CompromiseEngine 计算候选集 -> 调用 MCP Tool 获取影片元数据 -> 生成 Proposal 分发至各 PreferenceAgent
* 反馈流：PreferenceAgent -> 对 Proposal 评分 + 定性反馈 -> Mediator 聚合计算 GroupSatisfaction -> 写入 VectorStore 并输出最终结果

## 2.4 部署拓扑（Deployment Topology）

MVP 阶段采用单机容器化部署，架构可平滑扩展至分布式：

* 本地模式（MVP）：所有组件运行于单一 Docker Container，LLM 通过 DeepSeek API 调用，Chroma 使用内存模式
* 扩展模式（生产）：LangGraph 状态机部署为独立 Service，Chroma 升级为持久化 Server，各 MCP Server 可独立部署与水平扩展

降级策略：LLM API 不可用时自动切换至 Ollama 本地模型；Chroma 不可用时退化为 JSON 文件存储

