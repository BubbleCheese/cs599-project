# Social Consensus Agent（群体协商观影 Agent）

> 不是给"你"推荐，而是给"你们"推荐——宿舍 4 人、情侣 2 人、家庭 N 人，Agent 模拟各方代表协商出妥协方案。

## 项目简介

基于多智能体协作（Multi-Agent Collaboration）的群体观影决策系统。每个用户由一个 **Preference Agent** 代表，**Mediator Agent** 负责协调冲突、提出妥协方案，最终输出群体满意度最大化的观影推荐。

## 方向

方向一：Agentic AI 原生开发

## 技术栈

| 类别 | 选型 | 说明 |
|------|------|------|
| AI IDE | Trae CN | 课程指定 |
| LLM | DeepSeek API / Ollama | DeepSeek 在线 + Ollama 本地降级 |
| Agent 框架 | 自定义状态机（LangGraph-ready） | MVP 自定义实现，预留 LangGraph 迁移接口 |
| 向量数据库 | Chroma（MVP 降级为内存字典） | 群体历史记录与满意度反馈 |
| MCP 协议 | MCP SDK（预留接口） | 豆瓣/IMDb/日历 API |
| 容器化 | Docker | Demo 环境可复现 |
| 编程语言 | Python 3.11+ | LangGraph 生态最成熟 |

## 目录结构

```
cs599-project/
├── docs/                          # 项目文档
│   ├── CS599_01_Design.docx      # 设计文档（Milestone 1）
│   ├── CS599_02_Spec.docx        # SDD 规格文档（Milestone 1）
│   ├── architecture.png          # 系统架构图
│   ├── state_machine.png         # 状态机图
│   └── spec/                     # SDD 规格文档（Markdown 版）
│       ├── product_spec.md
│       ├── arch_spec.md
│       └── api_spec.md
├── src/                          # 源代码
│   ├── agents/                   # Agent 定义
│   │   ├── preference_agent.py   # Preference Agent（偏好解析、投票）
│   │   └── mediator_agent.py     # Mediator Agent（冲突检测、提案生成）
│   ├── graph/                    # 状态机
│   │   └── consensus_graph.py    # LangGraph 风格协商流程（6 状态闭环）
│   ├── models/                   # 数据模型
│   │   └── schemas.py            # Pydantic 数据模型
│   ├── data/                     # 数据
│   │   └── movies.py             # 模拟影片数据（50 部）
│   └── __init__.py
├── tests/                        # 测试（待补充）
├── main.py                       # 入口文件
├── requirements.txt              # 依赖
├── .env.example                  # 环境变量模板
├── .gitignore                    # 排除 API Key
└── README.md                     # 本文件
```

## 环境搭建

### 1. 依赖安装

```bash
pip install -r requirements.txt
```

### 2. 环境变量配置（可选）

```bash
cp .env.example .env
# 编辑 .env 填入 DeepSeek API Key（用于后续 LLM 升级）
```

> **注意**：MVP 版本不依赖外部 LLM API，所有 Agent 逻辑基于规则引擎实现，可直接运行。

### 3. 启动步骤

```bash
# 运行全部 4 个 Demo 场景
python main.py

# 运行单个场景
python main.py --scenario 1

# 交互模式（输入自定义偏好）
python main.py --custom
```

## 项目状态

- [x] Milestone 1: Proposal（设计文档 + 架构图 + Spec 初稿）
- [x] Milestone 2: MVP（核心闭环 Demo，tag: v0.1）
- [ ] Final Demo（集成测试 + 完整报告）

## 核心闭环 Demo

MVP 实现了完整的 6 状态协商闭环：

```
collect_prefs -> detect_conflict -> [resolve] -> generate_proposal -> collect_votes -> final_decision
                                                              |                                      
                                                              v                                      
                                                           fallback (R5 安全牌兜底)
```

### Demo 场景

| 场景 | 描述 | 协商轮次 | 结果 |
|------|------|---------|------|
| 场景 1 | 科幻爱好者 vs 喜剧爱好者 | 3 轮 | 《怦然心动》满意度 9.0 |
| 场景 2 | 恐怖片红线（一方绝对不接受） | 1 轮 | 《肖申克的救赎》满意度 8.0 |
| 场景 3 | 高要求 vs 随意 | 1 轮 | 《肖申克的救赎》满意度 8.0 |
| 场景 4 | 极端冲突（几乎无交集） | 1 轮 | 《怦然心动》满意度 9.0 |

### 协商过程示例

```
Alice: "我喜欢科幻片，时长不要超过120分钟，不要恐怖片"
Bob:   "我想看喜剧片，轻松一点的，时长90分钟以内最好"

[协商过程]
  提案 #1: 《美丽人生》(116min) → Bob 否决(时长超限)
  提案 #2: 《疯狂动物城》(108min) → Bob 否决(时长超限)
  提案 #3: 《怦然心动》(90min) → Alice 赞成(8分) + Bob 赞成(10分)

[最终结果] 《怦然心动》群体满意度 9.0/10
```

## 开源协议

MIT License
