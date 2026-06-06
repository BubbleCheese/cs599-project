**Social Consensus Agent**

**群体协商观影智能体**

**设计文档**

CS599 企业级应用软件设计与开发

方向一：Agentic AI 原生开发

姓名：徐珂

学号：２０２５３０２９９８

指导教师：戚欣

2026 年 6 月

# 一、项目概述

## 1.1 一句话定位

本项目完成一个用于推荐影片的Agent

不仅仅是给单人推荐，而且给"你们"推荐，例如宿舍 4 人、情侣 2 人、家庭 N 人，Agent 模拟各方代表协商出妥协方案。

Social Consensus Agent 是一个基于多智能体协作的群体决策系统。它不针对单个用户进行偏好优化，而是将群体观影视为一个多目标博弈问题：每个成员由一个专属的 Preference Agent 代表，Mediator Agent 负责协调各方利益、提出妥协方案，最终输出一个群体满意度最大化的观影推荐。

## 1.2 痛点分析

多人一起看电影或选书时，常常面临以下困境：

* 偏好冲突：A 热爱科幻大片，B 对恐怖片零容忍，C 只希望时长控制在 90 分钟以内
* 协调成本高：人工询问每个人的偏好、反复比较选项、多次协商耗费大量时间
* 安全牌困境：最终往往选择一个"大家都觉得还行但谁都不满意"的中间选项，群体体验被拉低
* 历史遗忘：上一次选了恐怖片导致张三评分仅 2/10，但下次推荐时系统完全遗忘这段经历

传统推荐系统本质上是单用户优化问题，面对群体场景时力不从心。本系统旨在通过多智能体协作机制，将群体决策过程自动化、智能化。

## 1.3 创新性与价值

本项目在以下方面具有显著创新性：

* 多目标博弈框架：将群体推荐建模为多智能体协商问题，天然契合课设"多智能体协作"的核心要求
* 现场演示效果极强：答辩时可现场展示 3 个 Agent 的"吵架-协商-和解"全过程，极具视觉冲击力
* 记忆增强决策：向量数据库存储群体历史观影记录与满意度反馈，实现进化式推荐
* MCP 协议实践：通过 MCP / Function Calling 接入豆瓣、IMDb 等外部 API，体现企业级 Agent 的工具使用能力

项目价值不仅在于技术实现，更在于展现了 Agentic AI 在真实社交场景中的应用潜力，具备从课设向产品演进的完整路径。

# 二、技术路线与核心选型

## 2.1 核心技术要素

本项目涵盖课程要求的 6 项核心技术要素中的 4 项以上：

|**核心技术要素**|**本项目的应用方式**|**对应章节**|
|-|-|-|
|SDD 规格驱动开发|Product/Arch/API 三份 Spec 文档|第五章（见 Spec 文档）|
|多智能体协作|Preference Agent x N + Mediator Agent|第四章|
|记忆机制|Chroma 向量数据库存储群体历史与反馈|第五章|
|状态管理|LangGraph 编排协商状态机（6 状态）|第三章|
|MCP / Function Calling|接入豆瓣/IMDb/日历 API|第五章|
|可观测性|协商日志 + 群体满意度 Benchmark|第六章|

## 2.2 技术栈选型

综合考量生态成熟度、课设时间约束和演示效果，选定以下技术栈：

|**类别**|**选型**|**说明**|
|-|-|-|
|AI IDE|Trae CN|课程指定|
|LLM|DeepSeek API|高性价比，备选 Ollama|
|Agent 框架|LangGraph|状态机语义匹配协商流程|
|向量数据库|Chroma|轻量，与 LangChain 集成好|
|MCP 协议|MCP SDK|标准化工具接口|
|容器化|Docker|确保 Demo 可复现|
|编程语言|Python 3.11+|LangGraph 生态最成熟|

技术选型理由：（1）LangGraph 的状态机语义与协商流程天然匹配，图形化展示效果好；（2）DeepSeek API 性价比优异，适合课设阶段的频繁调试；（3）Trae CN 作为课程指定 IDE，具备自适应 AI 原生开发能力；（4）Docker 确保 Demo 环境的可复现性。

# 三、系统架构设计

## 3.1 整体架构

系统采用分层架构设计，自上而下分为用户层、智能体层、编排层、记忆层和工具层。整体架构如下图所示：

!\[Social Consensus Agent 五层架构图](demo/arch\_struct.png)

图1：Social Consensus Agent 系统架构图

架构说明：

* 用户层：群体成员（2-N 人），每人拥有独立的偏好画像
* 智能体层：每个用户对应一个 Preference Agent；Mediator Agent 作为调解者居中协调
* 编排层：LangGraph 状态机驱动整个协商流程，确保状态转换的可控性和可观测性
* 记忆层：向量数据库（Chroma）持久化群体观影历史与满意度反馈
* 工具层：通过 MCP 协议接入豆瓣 API、IMDb API、日历 API

## 3.2 LangGraph 状态机

系统核心是一个由 LangGraph 编排的有限状态机，定义了从偏好收集到最终裁决的完整协商流程：

!\[协商状态流转流程图](demo/langgraph\_flow.png)

图2：LangGraph 状态机 — 协商工作流

状态说明：

* collect\_prefs：收集所有 Preference Agent 的观影偏好
* detect\_conflict：检测偏好冲突（类型互斥、时长超限等）
* resolve：冲突不可调和时，Mediator Agent 启动妥协规则
* generate\_proposal：基于协调后的偏好生成候选影片提案
* collect\_votes：各 Preference Agent 对提案投票
* final\_decision：达成群体共识，输出最终推荐

状态转换条件与边界：任何状态可在超时后触发 ESCALATE 进入 resolve；若 resolve 失败超过最大轮次则进入 fallback 状态，推荐安全牌影片。

# 四、多智能体协作设计

## 4.1 Preference Agent

每个群体成员对应一个 Preference Agent，是该用户在系统中的"数字代言人"。其核心职责包括：

* 偏好表达：将用户自然语言偏好转化为结构化偏好向量
* 利益维护：坚守核心红线，对触及红线的提案行使否决权
* 灵活妥协：在非核心偏好上保留让步空间
* 投票反馈：对提案评分（1-10 分）并提供定性反馈

Prompt 设计要点：在 System Prompt 中明确定义"硬约束"和"软偏好"，通过 few-shot 示例训练协商策略。

## 4.2 Mediator Agent

Mediator Agent 是协商过程的核心协调者，相当于"智能会议主持人"。核心职责：

* 冲突识别：分析各 Preference Agent 的偏好向量，识别不可调和冲突
* 方案生成：基于妥协规则生成满足最大公约数的候选方案
* 议程管理：控制协商轮次，防止无限循环
* 裁决权：投票无法达成一致时，基于历史满意度数据做出最终裁决

# 五、记忆与工具设计

## 5.1 向量数据库记忆机制

记忆层采用 Chroma 向量数据库，存储三类信息：

* 群体观影记录：影片 ID、类型、时长、共识达成轮次等元数据
* 满意度反馈：每个成员对每次观影的评分（1-10）和文字评价
* 偏好画像：每个成员的长期偏好向量，随反馈动态更新

检索策略：Mediator Agent 向量化查询当前偏好组合，检索历史上相似决策结果及满意度，作为决策参考。

## 5.2 MCP / Function Calling 设计

系统通过 MCP 协议接入外部工具：

|**工具**|**MCP Server**|**功能说明**|
|-|-|-|
|豆瓣 API|douban\_mcp.py|获取影片元数据（类型、时长、评分、简介）|
|IMDb API|imdb\_mcp.py|获取国际影片信息、多语言标题|
|日历 API|calendar\_mcp.py|过滤时长约束（如"今晚只有 2 小时"）|

MCP 协议的优势在于将工具接口标准化，新增工具只需注册新的 MCP Server，无需修改 Agent 核心逻辑。

# 六、MVP 开发与里程碑

## 6.1 MVP 简化路径

为确保在课设时间约束内完成可运行的 Demo，MVP 版本做以下简化：

* 群体规模：2 个虚拟用户 + 1 个 Mediator
* 协商维度：仅"类型 + 时长"
* 数据源：本地模拟影片数据（50 部）
* 记忆层：内存字典代替 Chroma
* LLM：DeepSeek API，备选 Ollama 本地模型
* MVP 目标：2 周内跑通完整协商闭环——输入偏好描述，Agent 完成多轮对话，输出最终推荐和协商日志。

## 6.2 开发时间表

|**阶段**|**时间**|**交付物**|
|-|-|-|
|Milestone 1: Proposal|第 13 周 (\~06.01)|设计文档、架构图、GitHub 仓库、Spec 初稿|
|Milestone 2: MVP|第 14 周 (\~06.08)|核心闭环 Demo，tag: v0.1|
|集成测试|第 15 周 (\~06.15)|接入真实 API、完善记忆层|
|Final Demo Day|第 16 周 (\~06.22)|现场演示 5min + 答辩 3min|

# 七、GitHub 仓库规划

仓库统一命名为 cs599-project，目录结构如下：

cs599-project/

├── docs/ # 项目文档

│ ├── CS599\_大作业报告.pdf # 最终报告

│ ├── proposal\&architecture.md # Milestone 1 Proposal和架构设计文档

│ └── spec/ # SDD 规格文档

│ ├── negotiation\_protocol.md

│ ├── compromise\_rules.md

│ └── veto\_conditions.md

├── src/ # 源代码

│ ├── agents/ # Agent 定义

│ │ ├── preference\_agent.py # Preference Agent

│ │ └── mediator\_agent.py # Mediator Agent

│ ├── graph/ # LangGraph 状态机

│ │ └── consensus\_graph.py # 协商流程图定义

│ ├── memory/ # 记忆层

│ │ └── vector\_store.py # Chroma 向量数据库封装

│ ├── tools/ # MCP 工具层

│ │ ├── douban\_mcp.py # 豆瓣 API MCP Server

│ │ ├── imdb\_mcp.py # IMDb API MCP Server

│ │ └── calendar\_mcp.py # 日历 API MCP Server

│ ├── models/ # 数据模型

│ │ └── schemas.py # Pydantic 数据模型

│ ├── config.py # 配置文件

│ └── main.py # 入口文件

├── tests/ # 测试

│ ├── test\_agents.py

│ └── test\_graph.py

├── data/ # 数据（影片模拟数据）

│ └── movies.json

├── docker-compose.yml # Docker 编排

├── Dockerfile

├── requirements.txt

├── README.md # 项目入口（必填）

├── .gitignore # 排除编译文件和 API Key

└── LICENSE # MIT 协议（Public Repo）

仓库管理规范：API Key 统一使用环境变量；每次提交需清晰 commit message；Milestone 2 打 tag v0.1，Final 打 tag v1.0；README 标注引用来源。

**Social Consensus Agent**

**设计文档**

CS599 企业级应用软件设计与开发 | 2026

