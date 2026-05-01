# GraphMind - 个人知识图谱与间隔复习系统

结合知识图谱（GraphRAG）与间隔复习（FSRS）的个人知识管理系统。

## 核心功能

- **笔记导入** - 从 Notion、Markdown 或 PDF 导入笔记
- **图谱构建** - 使用 LLM 从笔记内容中提取实体和关系，存入 Neo4j
- **图谱检索** - GraphRAG（局部搜索 + 全局搜索）进行问答和知识发现
- **间隔复习** - 基于 FSRS 算法的闪卡复习系统，科学安排复习时间

## 技术栈

| 层级 | 技术 |
|------|------|
| Web 框架 | FastAPI + uvicorn |
| 图数据库 | Neo4j 5.25（Docker） |
| Embedding | Ollama 本地模型（nomic-embed-text） |
| 生成模型 | MiniMax API（MiniMax-M2） |
| 复习算法 | FSRS（Free Spaced Repetition Scheduler） |

## 快速开始

```bash
# 1. 启动 Neo4j
docker-compose up -d

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置环境变量
cp .env.example .env  # 填入 API Key

# 4. 启动服务
python -m app.main
# API 文档：http://localhost:8000/docs
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
│   │   ├── deep_review.py   # GET /deep-review/session, POST /deep-review/generate
│   │   ├── entities.py     # GET /entities/, /entities/{id}
│   │   └── pdf_import.py    # POST /pdf/import
│   ├── core/                # 核心业务逻辑
│   │   ├── database.py      # Neo4jDatabase：异步连接、查询、索引初始化
│   │   ├── embedding.py     # OllamaEmbedding：本地向量化
│   │   ├── parser.py        # Markdown 解析，frontmatter 提取，按标题/段落分块
│   │   ├── graph_builder.py # GraphBuilder：实体/关系 LLM 提取，Neo4j 存储
│   │   ├── rag_engine.py    # RAGEngine：local_search（向量+图邻域），global_search（社区检测）
│   │   ├── notion_importer.py # NotionImporter：Notion blocks → Markdown
│   │   └── pdf_parser.py    # PDF 解析
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
│   ├── notes/               # Markdown 笔记文件
│   └── pdfs/                # PDF 源文件
├── scripts/
│   ├── build_graph.py           # 全量图谱构建脚本
│   ├── build_graph_filtered.py  # 仅构建金融/科技标签内容的图谱
│   ├── cli_review.py            # CLI 闪卡复习工具
│   ├── generate_reviews.py       # 预生成深度复习内容
│   ├── import_notion_full.py    # 全量 Notion 导入脚本
│   ├── import_pdf.py            # PDF 导入脚本
│   ├── schedule_review.py        # 定时复习任务调度（08:00 / 20:00）
│   └── generate_business_plan.py # 生成 GraphMind 商业计划 PDF
├── tests/
├── requirements.txt
├── docker-compose.yml
└── .env.example
```

## 核心脚本

| 脚本 | 用途 |
|------|------|
| `build_graph.py` | 从所有 Chunk 构建图谱（实体+关系） |
| `build_graph_filtered.py --tags 金融,科技` | 按标签过滤构建 |
| `cli_review.py` | CLI 闪卡复习 |
| `generate_reviews.py --finance` | 生成金融类深度复习 |
| `import_pdf.py --path <pdf_path>` | 导入 PDF 到图谱 |
| `import_notion_full.py` | 从 Notion 导入所有页面为 Markdown |
| `schedule_review.py` | 定时复习提醒（08:00 / 20:00） |

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
