# GraphMind - 个人知识图谱与间隔复习系统

## 项目概述

GraphMind 是一个结合知识图谱（GraphRAG）与间隔复习（FSRS）的个人知识管理系统。核心功能：

1. **笔记导入** - 从 Notion 或 Markdown 文件导入笔记
2. **图谱构建** - 使用 LLM 从笔记内容中提取实体和关系，存入 Neo4j
3. **图谱检索** - GraphRAG（局部搜索 + 全局搜索）进行问答和知识发现
4. **间隔复习** - 基于 FSRS 算法的闪卡复习系统，科学安排复习时间

## 技术栈

| 层级 | 技术 |
|------|------|
| Web 框架 | FastAPI + uvicorn |
| 图数据库 | Neo4j 5.25（Docker） |
| Embedding | Ollama 本地模型（nomic-embed-text） |
| 生成模型 | MiniMax API（MiniMax-M2） |
| 复习算法 | FSRS（Free Spaced Repetition Scheduler） |
| 笔记格式 | Markdown + frontmatter |

## 架构图

```
┌─────────────────────────────────────────────────────────────┐
│                        用户层                                │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────────┐  │
│  │ CLI 复习  │  │ FastAPI  │  │ Notion   │  │ 商业计划    │  │
│  │ cli_review│  │ Web API  │  │ 导入脚本  │  │ PDF 生成    │  │
│  └──────────┘  └──────────┘  └──────────┘  └─────────────┘  │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                       核心模块层                              │
│  ┌────────────┐  ┌─────────────┐  ┌──────────────────────┐   │
│  │ parser.py  │  │ graph_builder│  │ rag_engine.py        │   │
│  │ Markdown   │  │ 实体/关系    │  │ 局部 + 全局搜索       │   │
│  │ 解析分块   │  │ 提取存储    │  │                      │   │
│  └────────────┘  └─────────────┘  └──────────────────────┘   │
│  ┌────────────┐  ┌─────────────┐  ┌──────────────────────┐   │
│  │ embedding  │  │ fsrs.py     │  │ deep_review.py       │   │
│  │ Ollama     │  │ FSRS 算法   │  │ 挑战性问题预生成      │   │
│  │ 向量化     │  │ 间隔调度    │  │                      │   │
│  └────────────┘  └─────────────┘  └──────────────────────┘   │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                       Neo4j 图数据库                         │
│  节点: Note, Chunk, Entity, Card, DeepReview                │
│  关系: CONTAINS, MENTIONS, RELATES_TO, NEXT, PREV, etc.     │
└─────────────────────────────────────────────────────────────┘
```

## 目录结构

```
knowledge_graph/
├── app/
│   ├── main.py              # FastAPI 入口，lifespan 事件，CORS 路由注册
│   ├── config.py            # pydantic-settings 配置类，读取 .env
│   ├── api/                 # REST API 端点
│   │   ├── notes.py         # POST /notes/import, GET /notes/, GET /notes/stats
│   │   ├── search.py        # POST /search/rag, /search/local/{id}, /search/entity/{id}
│   │   ├── review.py        # GET /review/queue, /review/stats, CRUD /review/{card_id}
│   │   └── deep_review.py   # GET /deep-review/session, POST /deep-review/generate
│   ├── core/                # 核心业务逻辑
│   │   ├── database.py      # Neo4jDatabase：异步连接、查询、索引初始化
│   │   ├── embedding.py     # OllamaEmbedding：本地向量化
│   │   ├── parser.py        # Markdown 解析，frontmatter 提取，按标题/段落分块
│   │   ├── graph_builder.py # GraphBuilder：实体/关系 LLM 提取，Neo4j 存储
│   │   ├── rag_engine.py    # RAGEngine：local_search（向量+图邻域），global_search（社区检测）
│   │   └── notion_importer.py # NotionImporter：Notion blocks → Markdown
│   ├── models/              # Pydantic 数据模型
│   │   ├── graph.py         # Entity, Relationship, EntityType, RelationshipType, Chunk
│   │   └── note.py          # Note, NoteChunk, Card, CardRating
│   ├── review/              # 复习系统
│   │   ├── fsrs.py          # FSRS 算法：stability_after_rating, difficulty_after_rating, calculate_next_review
│   │   ├── cards.py         # CardManager：Neo4j 中的卡片 CRUD
│   │   ├── scheduler.py     # ReviewScheduler：复习队列、统计、图谱优先级
│   │   └── deep_review.py   # DeepReviewEngine：预生成挑战性问题
│   └── utils/
│       └── notification.py  # Windows 蜂鸣提示
├── data/
│   ├── notes/               # ~100 个 Markdown 笔记文件（来自 Notion 导入）
│   └── sample_cards.json    # 示例闪卡数据
├── tests/
│   └── __init__.py          # （暂无测试文件）
├── build_graph.py           # 全量图谱构建脚本
├── build_graph_filtered.py  # 仅构建金融/科技标签内容的图谱
├── cli_review.py            # CLI 闪卡复习工具
├── generate_reviews.py      # 预生成深度复习内容
├── generate_business_plan.py # 生成 GraphMind 商业计划 PDF
├── import_notion_full.py    # 全量 Notion 导入脚本
├── schedule_review.py        # 定时复习任务调度（08:00 / 20:00）
├── requirements.txt         # Python 依赖
├── docker-compose.yml       # Neo4j 5.25 容器配置
└── .env.example             # 环境变量模板
```

## Neo4j 数据模型

### 节点类型

| 节点 | 属性 | 说明 |
|------|------|------|
| `Note` | id, title, source, created_at | 笔记文档 |
| `Chunk` | id, content, frontmatter, chunk_index | 笔记分块 |
| `Entity` | id, name, type, description, properties | 实体（概念/技术/工具/人物等） |
| `Card` | id, front_text, back_text, due, interval, stability, difficulty | 闪卡 |
| `DeepReview` | id, entity_id, question, answer, status | 预生成深度问题 |

### 关系类型

| 关系 | 说明 |
|------|------|
| `NOTE:CONTAINS→Chunk` | 笔记包含分块 |
| `Chunk:CONTAINS→Entity` | 分块提及实体 |
| `Entity:RELATES_TO→Entity` | 实体间关系 |
| `Entity:MENTIONS→Chunk` | 实体关联的分块 |
| `Card:NEXT→Card` | 复习顺序 |

## 启动方式

```bash
# 1. 启动 Neo4j
docker-compose up -d

# 2. 安装依赖
pip install -r requirements.txt

# 3. 启动 API 服务
python -m app.main
# 或 uvicorn app.main:app --reload --port 8000

# 4. 启动定时复习任务
python schedule_review.py
```

## 核心脚本

| 脚本 | 用途 |
|------|------|
| `build_graph.py` | 从所有 Chunk 构建图谱（实体+关系） |
| `build_graph_filtered.py` | 仅从金融/科技标签 Chunk 构建图谱 |
| `cli_review.py` | CLI 闪卡复习（python cli_review.py） |
| `generate_reviews.py` | 预生成深度复习内容 |
| `import_notion_full.py` | 从 Notion 导入所有页面为 Markdown |

### generate_reviews.py 用法
```bash
python generate_reviews.py              # 全部分类
python generate_reviews.py --finance    # 仅金融
python generate_reviews.py --tech --count 30  # 科技，30 条
```

## 环境变量

```bash
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password
MINIMAX_API_KEY=your_minimax_api_key
MINIMAX_API_BASE=https://api.minimax.chat
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_EMBEDDING_MODEL=nomic-embed-text
NOTION_API_KEY=your_notion_api_key
APP_HOST=0.0.0.0
APP_PORT=8000
```

## API 端点

### 笔记
- `POST /notes/import` - 导入笔记到 Neo4j
- `GET /notes/` - 列出所有笔记
- `GET /notes/{note_id}` - 获取笔记详情
- `GET /notes/stats` - 获取统计信息

### 搜索
- `POST /search/rag` - GraphRAG 问答搜索
- `GET /search/local/{entity_id}` - 局部搜索（图邻域）
- `GET /search/entity/{entity_id}` - 获取实体详情
- `GET /search/graph/sample` - 采样图谱数据
- `GET /search/communities` - 获取社区结构

### 复习
- `GET /review/queue` - 获取今日复习队列
- `GET /review/stats` - 获取复习统计
- `GET/POST/DELETE /review/{card_id}` - 卡片 CRUD

### 深度复习
- `GET /deep-review/session` - 获取深度复习 session
- `POST /deep-review/generate` - 生成深度复习内容
- `POST /deep-review/evaluate` - 评估回答质量

## FSRS 复习算法

FSRS（Free Spaced Repetition Scheduler）核心公式：

- **Stability** (S): 记忆稳定度，决定下次复习间隔
- **Difficulty** (D): 卡片难度 (0-1)
- **Rating**: 评分 1-4（忘记/模糊/记住/完美）

每次复习后更新 S 和 D，下一次复习间隔 = f(S, D, rating)。

## 版本控制流程

采用 **Trunk-Based Development**（单分支流），适合个人项目：

### 分支策略
- `master` - 稳定代码，始终可部署
- 功能开发直接在 master 上进行，频繁提交

### 提交规范
```
<类型>: <简短描述>

可选的详细说明

类型: feat | fix | docs | refactor | test | chore
```

### 开发流程
```bash
# 1. 开始新功能或修复
git checkout master
git pull origin master

# 2. 开发，频繁提交
git add .
git commit -m "feat: 添加新功能"

# 3. 推送到远程
git push origin master
```

### 禁止操作
- **禁止** `git push --force` 到 master（除非修复敏感信息泄露）
- **禁止** 提交 `.env`、密钥、token
- **禁止** 在 commit message 中包含真实 API Key

### 修复敏感信息泄露流程
若意外提交了密钥，执行：
```bash
git filter-repo --path <file> --invert-paths --force
git push --force
```
然后在 GitHub 设置页解除对该 secret 的警报。

## 待办事项（TODO）

以下为待实现功能的记录，按优先级排序：

- [ ] 将图谱划分为金融/技术两个子网络，减少单次计算量
- [ ] 支持 Onenote 导入
- [ ] 实现节点管理功能（删除、收藏、搜索列表看板）
- [ ] 提前自动生成复习内容，而非临时生成

## debug
- 界面显示问题：
    - 点击收藏按钮后，由原先的15条变成了“共1条预生成内容”，再次点击收藏按钮（取消收藏）后，又变回了15条。
    - 点击保留/丢弃卡片并确认后卡片仍在队列中。

## 功能改进
- 删除左侧顶部的知识复习字样以及下方的总卡片、待复习框