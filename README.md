# GraphMind

结合知识图谱（GraphRAG）与间隔复习（FSRS）的个人知识管理系统。

## 核心功能

- **笔记导入** - 从 Notion 或 Markdown 文件导入笔记
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

### 1. 启动 Neo4j

```bash
docker-compose up -d
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置环境变量

复制 `.env.example` 为 `.env`，填入你的 API Key。

### 4. 启动服务

```bash
python -m app.main
```

API 文档：http://localhost:8000/docs

## 目录结构

```
knowledge_graph/
├── app/
│   ├── api/          # REST API 端点
│   ├── core/         # 核心业务逻辑（图谱/嵌入/RAG）
│   ├── models/       # Pydantic 数据模型
│   └── review/       # 复习系统（FSRS）
├── data/notes/       # Markdown 笔记源文件
├── build_graph.py    # 图谱构建脚本
├── cli_review.py     # CLI 闪卡复习
└── generate_reviews.py # 深度复习内容生成
```

## 常用脚本

| 脚本 | 用途 |
|------|------|
| `build_graph.py` | 从所有笔记构建图谱 |
| `cli_review.py` | CLI 闪卡复习 |
| `generate_reviews.py --finance` | 生成金融类深度复习 |

## 版本历史

| 版本 | 日期 | 更新内容 |
|------|------|----------|
| v0.1.0 | 2026-04-28 | 初始版本：GraphRAG + FSRS 基础功能 |
