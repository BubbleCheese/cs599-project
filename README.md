# Social Consensus Agent（群体协商观影 Agent）

> 不是给"你"推荐，而是给"你们"推荐——宿舍 4 人、情侣 2 人、家庭 N 人，Agent 模拟各方代表协商出妥协方案。

## 项目简介

基于**多智能体协作（Multi-Agent Collaboration）**的群体观影决策系统。每个用户由一个 **Preference Agent** 代表，**Mediator Agent** 负责协调冲突、提出妥协方案，最终输出群体满意度最大化的观影推荐。

**核心特性：**
- 🤖 **LLM 增强**：集成 DeepSeek API，支持自然语言偏好解析
- 🧠 **向量存储**：ChromaDB 持久化 + 内存临时存储分层架构
- 🎬 **豆瓣集成**：实时从豆瓣获取电影信息
- 🌐 **Web 前端**：可视化展示协商全过程，支持动态添加 N 个用户
- 🔄 **状态机驱动**：6 状态闭环，实时展示协商流程

## 方向

方向一：Agentic AI 原生开发

## 技术栈

### 后端
| 类别 | 选型 | 说明 |
|------|------|------|
| Web API | FastAPI + Uvicorn | RESTful API，CORS 支持 |
| LLM | DeepSeek API / Mock | DeepSeek 在线调用，无 Key 时自动回退规则引擎 |
| Agent 框架 | 自定义状态机 (LangGraph-ready) | 6 状态闭环 |
| 向量数据库 | Chroma / Memory | 语义检索，未安装时自动回退内存 |
| MCP 协议 | MCP SDK (自定义实现) | 豆瓣 API，无 Key 时回退本地库 |
| 编程语言 | Python 3.11+ | Pydantic + FastAPI + pytest |

### 前端
| 类别 | 选型 | 说明 |
|------|------|------|
| 技术 | HTML5 + Tailwind CSS CDN | 零构建，纯原生实现 |
| 交互 | Vanilla JavaScript | Fetch API 调用后端 |
| 可视化 | CSS 动画 + 状态机组件 | 6 状态实时高亮 |

## 目录结构

```
cs599-project/
├── src/
│   ├── agents/
│   │   ├── preference_agent.py   # PreferenceAgent: LLM增强偏好解析 + 投票
│   │   └── mediator_agent.py     # MediatorAgent: 冲突检测 + 妥协规则(R1-R5) + Chroma历史加权
│   ├── api/
│   │   └── server.py             # FastAPI 后端服务 (4个API端点)
│   ├── graph/
│   │   └── consensus_graph.py    # LangGraph风格6状态闭环
│   ├── llm/
│   │   ├── base.py               # LLM抽象基类
│   │   ├── deepseek.py           # DeepSeek API适配器 + Prompt模板
│   │   └── mock.py               # Mock LLM (规则引擎回退)
│   ├── memory/
│   │   └── vector_store.py       # Chroma向量数据库 / 内存回退
│   ├── models/
│   │   └── schemas.py            # Pydantic数据模型
│   ├── tools/
│   │   └── douban_mcp.py         # 豆瓣MCP Server (API / 本地回退)
│   └── data/
│       └── movies.py             # 50部模拟影片 + 搜索API
├── web/                          # 【前端】Web UI
│   └── index.html                # 可视化界面 (单文件HTML)
├── tests/
│   ├── test_agents.py            # Agent单元测试 (18个)
│   ├── test_graph.py             # 状态机测试 (12个)
│   └── test_scenarios.py         # 场景集成测试 (21个)
├── docs/
│   ├── CS599_01_Design.docx      # 设计文档 (Milestone 1)
│   ├── CS599_02_Spec.docx        # SDD规格文档 (Milestone 1)
│   ├── architecture.png          # 系统架构图
│   └── state_machine.png         # 状态机图
├── main.py                       # CLI入口 (5个场景 + 交互模式)
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

## 快速开始

### 1. 环境搭建

```bash
cd cs599-project
pip install -r requirements.txt
```

### 2. 配置环境变量（可选）

复制 `.env.example` 为 `.env` 并配置 API keys：

```bash
cp .env.example .env
```

编辑 `.env` 文件：

```bash
# DeepSeek API (用于 LLM 增强功能)
DEEPSEEK_API_KEY=your_deepseek_api_key_here
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1

# ChromaDB (用于持久化向量存储)
CHROMA_PERSIST_DIR=./chroma_db
```


### 3. 启动后端 API 服务

```bash
# 启动 FastAPI 服务 (默认端口 8000)
python -m uvicorn src.api.server:app --reload --port 8000

# 服务启动后访问:
# API 文档: http://localhost:8000/docs
# 前端页面: http://localhost:8000/web/index.html
```

### 3. 打开前端页面

**方式一：通过 FastAPI 自动服务** (推荐)

FastAPI 会自动 serve `web/index.html`，直接访问：
```
http://localhost:8000/web/index.html
```

**方式二：直接用浏览器打开**

```bash
# 用浏览器打开 web/index.html 文件即可
# macOS:
open web/index.html
# Linux:
xdg-open web/index.html
# 或直接用浏览器拖拽 index.html
```

> 注意：如果用方式二打开，需要确保后端服务已启动（跨域已配置允许 `*`）

### 4. CLI 模式 (无需前端)

```bash
# 运行全部5个场景
python main.py

# 运行单个场景
python main.py --scenario 4          # 4人宿舍场景
python main.py --scenario 5          # 6人家庭场景

# 交互模式 (支持N人自定义输入)
python main.py --custom
```

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/health` | 健康检查 |
| GET | `/api/scenarios` | 获取预设场景列表 |
| POST | `/api/negotiate` | 执行群体协商 |
| GET | `/api/movies` | 获取影片列表 |

### POST /api/negotiate 示例

```json
// Request
{
  "users": [
    {"name": "Alice", "preference": "我喜欢科幻片，不要恐怖片"},
    {"name": "Bob", "preference": "我喜欢喜剧片，90分钟以内"}
  ],
  "use_llm": true,
  "use_chroma": true
}

// Response
{
  "movie": { "movie_id": "sf07", "title": "地心引力", "genres": ["科幻", "惊悚"], ... },
  "group_score": 7.0,
  "votes": [ { "user_name": "Alice", "score": 8, "verdict": "approve", ... } ],
  "negotiation_log": [ "=== STATE: collect_prefs ===", ... ],
  "rounds_taken": 1,
  "dissenters": [],
  "is_fallback": false
}
```

**请求参数说明：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `users` | `Array` | 是 | 用户列表，每个用户包含 `name` 和 `preference` |
| `use_llm` | `Boolean` | 否 | 是否使用 LLM 增强功能（默认 `false`） |
| `use_chroma` | `Boolean` | 否 | 是否使用 ChromaDB 向量存储（默认 `false`） |

## 前端功能

- **👥 群体偏好输入**：动态添加/删除用户，输入自然语言偏好
- **🎯 预设场景**：一键加载 5 个 Demo 场景（2/4/6人）
- **🔄 状态机可视化**：6 个协商状态实时高亮显示流转过程
- **🎬 结果展示**：推荐影片卡片（片名、类型、时长、评分、满意度）
- **📊 投票详情**：每个用户的评分和理由
- **📝 协商日志**：完整的协商过程记录，按类型着色
- **🟢 后端状态检测**：实时显示后端服务在线状态
- **🤖 LLM 集成**：支持 DeepSeek API，无 Key 时自动回退规则引擎
- **🧠 向量存储**：支持 ChromaDB 持久化，未安装时自动回退内存
- **🎬 豆瓣搜索**：实时从豆瓣获取电影信息，失败时回退本地库

## 运行测试

```bash
# 全部 51 个测试
python -m pytest tests/ -v

# 运行特定测试文件
python -m pytest tests/test_agents.py -v
python -m pytest tests/test_graph.py -v
python -m pytest tests/test_scenarios.py -v
```

## 部署说明

### GitHub 部署

项目已配置好 `.gitignore`，保护敏感信息不被上传：

```bash
# 1. 初始化 Git 仓库（已完成）
git init

# 2. 添加文件（已完成）
git add .

# 3. 创建提交（已完成）
git commit -m "Initial commit: Social Consensus Agent project"

# 4. 添加远程仓库
git remote add origin https://github.com/用户名/仓库名.git

# 5. 推送到 GitHub
git push -u origin master
```

### 环境变量配置

在部署后，其他开发者需要：

1. 复制 `.env.example` 为 `.env`
2. 填入自己的 API keys
3. 运行 `pip install -r requirements.txt`
4. 启动服务：`python -m uvicorn src.api.server:app --reload --port 8000`

## 核心特性详解

### 1. LLM 增强（DeepSeek API）

- **自然语言偏好解析**：使用 DeepSeek API 解析用户的自然语言偏好
- **智能评分**：基于 LLM 的评分系统，更准确的用户满意度预测
- **自动回退**：无 API Key 时自动使用 Mock 引擎（规则引擎）

**配置方式：**
```bash
# 在 .env 文件中配置
DEEPSEEK_API_KEY=your_deepseek_api_key_here
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
```

### 2. 向量存储（ChromaDB + 内存）

- **分层存储架构**：
  - **临时偏好**：使用内存存储，一次协商会话
  - **历史记录**：使用 ChromaDB 持久化，跨会话记忆
  - **影片知识库**：使用 ChromaDB，语义检索
- **自动回退**：未安装 ChromaDB 时自动使用内存存储
- **语义检索**：基于向量相似度的影片推荐

**配置方式：**
```bash
# 在 .env 文件中配置
CHROMA_PERSIST_DIR=./chroma_db
```

### 3. 豆瓣电影集成

- **实时搜索**：从豆瓣电影搜索页面获取最新电影信息
- **丰富数据**：包含评分、类型、时长、封面等详细信息
- **自动回退**：豆瓣 API 失败时自动使用本地电影库
- **智能解析**：解析豆瓣页面内联 JSON 数据

**搜索示例：**
```python
from src.tools.douban_mcp import search

# 搜索电影
result = search(title='星际穿越', genres=['科幻'], rating_min=8.0, max_duration=180, limit=5)
```

### 4. Web 前端

- **单文件部署**：纯 HTML + JavaScript，无需构建工具
- **实时交互**：动态添加用户、实时显示协商过程
- **状态机可视化**：6 个协商状态实时高亮
- **响应式设计**：适配桌面和移动设备

**访问方式：**
```
http://localhost:8000/web/index.html
```

### 5. 状态机驱动

6 个协商状态闭环：

1. **collect_prefs** - 收集用户偏好
2. **analyze_conflicts** - 分析冲突
3. **propose_solutions** - 提出解决方案
4. **vote** - 投票
5. **check_consensus** - 检查共识
6. **finalize** - 最终确定

## 5 项 Final Demo 升级

| # | 升级项 | 核心文件 | 切换方式 |
|---|--------|---------|---------|
| 1 | **LLM 接入** | `src/llm/deepseek.py` + `mock.py` | `export DEEPSEEK_API_KEY="xxx"` → `--llm deepseek` |
| 2 | **Chroma 向量库** | `src/memory/vector_store.py` | `pip install chromadb` → `--chroma` |
| 3 | **豆瓣 MCP** | `src/tools/douban_mcp.py` | `export DOUBAN_API_KEY="xxx"` |
| 4 | **N 人扩展** | `main.py` + `consensus_graph.py` | `--scenario 4`(4人) / `--scenario 5`(6人) / `--custom`(N人) |
| 5 | **pytest 测试** | `tests/test_*.py` (51个) | `pytest tests/ -v` |
| 6 | **Web 前端** | `web/index.html` + `src/api/server.py` | `uvicorn src.api.server:app --port 8000` |

## 项目状态

- [x] Milestone 1: Proposal (设计文档 + 架构图 + Spec初稿)
- [x] Milestone 2: MVP (核心闭环Demo)
- [x] Final Demo:
  - [x] 接入真实LLM (DeepSeek API + Mock回退)
  - [x] 接入Chroma向量数据库 (语义检索 + 内存回退)
  - [x] 接入豆瓣电影搜索 (实时获取 + 本地回退)
  - [x] 扩展群体规模 (2人→N人)
  - [x] pytest测试 (51个测试全部通过)
  - [x] **Web前端** (FastAPI + 可视化UI)
  - [x] **GitHub 部署配置** (.gitignore + .env.example)

## 贡献指南

欢迎贡献代码！请遵循以下步骤：

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

## 许可证

MIT License

## 联系方式

如有问题或建议，请提交 Issue 或 Pull Request。
