#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

"""
构建知识图谱脚本 - 改进版
处理所有 chunk，详细提取实体和关系
"""

import asyncio
import json
import hashlib
import os
import httpx
from neo4j import AsyncGraphDatabase
from dotenv import load_dotenv

load_dotenv()

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

TOKEN_PLAN_BASE = "https://token-plan-cn.xiaomimimo.com/v1"
TOKEN_PLAN_KEY = "tp-clupk2hrhxfh411yeo7kk22o4mxbnqzgi5avazgs273y7gc8"
MODEL = "mimo-v2.5-pro"

# Token usage tracking
_total_tokens = 0
_api_calls = 0


def compute_id(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()[:12]


def safe_json_parse(text: str) -> list:
    """Safely parse JSON from LLM response"""
    try:
        start = text.find("[")
        end = text.rfind("]") + 1
        if start >= 0 and end > start:
            return json.loads(text[start:end])
    except json.JSONDecodeError:
        pass
    return []


TECH_KEYWORDS = ['机器学习', '深度学习', '神经网络', 'Python', 'RAG', 'Agent', 'LLM', 'Transformer',
                '算法', '模型', '训练', 'Embedding', '向量', 'NLP', 'CV', '计算机视觉', '语音',
                'AI', '人工智能', '大数据', '区块链', '云原生', '分布式', '微服务', 'API']

FINANCE_KEYWORDS = ['金融', '银行', '投资', '股票', '债券', '基金', '理财', '保险', '信贷',
                   '风控', '资产', '负债', '市值', '估值', '财报', '利润', '营收', '利率',
                   '汇率', '宏观经济', '货币政策', '财政政策', 'IPO', '并购', '重组']


def detect_category(content: str) -> str:
    """Detect if content is about finance or tech"""
    tech_score = sum(1 for kw in TECH_KEYWORDS if kw in content)
    finance_score = sum(1 for kw in FINANCE_KEYWORDS if kw in content)

    if tech_score > finance_score and tech_score >= 2:
        return 'tech'
    elif finance_score > tech_score and finance_score >= 2:
        return 'finance'
    elif tech_score >= 2:
        return 'tech'
    elif finance_score >= 2:
        return 'finance'
    return 'other'


async def chat_llm(prompt: str) -> str:
    """Call token-plan LLM API with retry on 429"""
    global _total_tokens, _api_calls
    for attempt in range(5):
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                response = await client.post(
                    f"{TOKEN_PLAN_BASE}/chat/completions",
                    headers={"Authorization": f"Bearer {TOKEN_PLAN_KEY}"},
                    json={"model": MODEL, "messages": [{"role": "user", "content": prompt}], "max_tokens": 2048}
                )
                if response.status_code == 429:
                    wait = 2 ** attempt
                    print(f"[WARN] Rate limited, retry in {wait}s (attempt {attempt+1}/5)")
                    await asyncio.sleep(wait)
                    continue
                response.raise_for_status()
                data = response.json()
                usage = data.get("usage", {})
                _total_tokens += usage.get("prompt_tokens", 0) + usage.get("completion_tokens", 0)
                _api_calls += 1
                return data["choices"][0]["message"]["content"]
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                wait = 2 ** attempt
                print(f"[WARN] Rate limited, retry in {wait}s (attempt {attempt+1}/5)")
                await asyncio.sleep(wait)
                continue
            raise
    raise Exception("Max retries exceeded for 429")


async def extract_entities(chunk_content: str, chunk_id: str) -> tuple[list[dict], str]:
    """Extract entities from chunk using token-plan LLM"""
    category = detect_category(chunk_content)

    prompt = f"""你是一个知识图谱专家。从以下文本中提取所有重要的概念、术语、技术、方法等实体。

要求：
1. 尽可能提取细粒度的实体（不仅仅是大的概念）
2. 每个实体都要有明确的含义
3. 实体类型统一使用: concept, technique, tool, person, organization, method, metric, file, event

输出格式（严格JSON数组）：
[
  {{"label":"实体名称","type":"实体类型","description":"简短描述"}}
]

文本内容（来自知识库 chunk {chunk_id}）：
---
{chunk_content[:1500]}
---

直接返回JSON数组，不要任何解释。数量尽可能多。"""

    try:
        text = await chat_llm(prompt)
        entities = safe_json_parse(text)

        valid = []
        for e in entities:
            if isinstance(e, dict) and "label" in e:
                label = e.get("label", "").strip()
                if len(label) < 2:
                    continue
                entity_id = compute_id(label) + "_" + e.get("type", "concept")[:4]
                e["id"] = entity_id[:30]
                e["type"] = e.get("type", "concept")
                e["description"] = e.get("description", "")[:100]
                e["category"] = category
                valid.append(e)
        return valid, category
    except Exception as e:
        print(f"[ERROR] extract_entities: {e}")
    return [], category


async def extract_relationships(entities: list[dict], chunk_content: str) -> list[dict]:
    """Extract relationships between entities using token-plan LLM"""
    if len(entities) < 2:
        return []

    entity_labels = [e["label"] for e in entities]

    prompt = f"""给定以下实体列表，分析它们在文本中的关系。

实体列表：{entity_labels}

文本内容：
{chunk_content[:1200]}

关系类型可选：
- relates_to: 一般关联
- part_of: 属于/组成
- uses: 使用/依赖
- implements: 实现
- defines: 定义
- describes: 描述
- caused_by: 导致
- compares: 比较
- depends_on: 取决于

输出格式（严格JSON数组）：
[
  {{"from":"实体A","to":"实体B","type":"关系类型"}}
]

只返回确实存在的关系，不要猜测。直接返回JSON数组。"""

    try:
        text = await chat_llm(prompt)
        return safe_json_parse(text)
    except Exception as e:
        print(f"[ERROR] extract_relationships: {e}")
    return []


async def process_chunk(driver, chunk_id: str, chunk_content: str):
    """Process a single chunk"""
    entities, category = await extract_entities(chunk_content, chunk_id)
    if not entities:
        return 0, 0

    stored_entities = 0
    stored_rels = 0

    async with driver.session() as session:
        # Store entities with MENTIONS relationship
        for entity in entities:
            entity_id = entity.get("id", "")
            label = entity.get("label", "")
            if not entity_id or not label:
                continue

            try:
                await session.run("""
                    MERGE (e:Entity {id: $id})
                    SET e.label = $label,
                        e.type = $type,
                        e.description = $description,
                        e.category = $category
                    WITH e
                    MATCH (c:Chunk {id: $chunk_id})
                    MERGE (e)-[:MENTIONS]->(c)
                    """,
                    id=entity_id,
                    label=label,
                    type=entity.get("type", "concept"),
                    description=entity.get("description", ""),
                    category=category,
                    chunk_id=chunk_id
                )
                stored_entities += 1
            except Exception as e:
                pass

        # Extract relationships between entities
        if len(entities) >= 2:
            rels = await extract_relationships(entities, chunk_content)
            for rel in rels:
                if not isinstance(rel, dict):
                    continue
                from_label = rel.get("from", "")
                to_label = rel.get("to", "")
                rel_type = rel.get("type", "relates_to")
                if from_label and to_label and from_label != to_label:
                    try:
                        await session.run("""
                            MATCH (e1:Entity {label: $from_label}), (e2:Entity {label: $to_label})
                            MERGE (e1)-[r:RELATES_TO]->(e2)
                            SET r.type = $rel_type
                            """,
                            from_label=from_label,
                            to_label=to_label,
                            rel_type=rel_type
                        )
                        stored_rels += 1
                    except:
                        pass

    return stored_entities, stored_rels


CONCURRENCY = 20  # 并发数


async def process_batch(driver, batch: list, total: int, progress_lock: asyncio.Lock):
    """并发处理一批 chunks"""
    tasks = []
    for chunk in batch:
        tasks.append(process_chunk(driver, chunk["chunk_id"], chunk["content"]))
    results = await asyncio.gather(*tasks, return_exceptions=True)

    async with progress_lock:
        total_entities = sum(r[0] if isinstance(r, tuple) else 0 for r in results)
        total_rels = sum(r[1] if isinstance(r, tuple) else 0 for r in results)
    return total_entities, total_rels


async def main():
    print("=" * 60)
    print("  Knowledge Graph Builder - Concurrent")
    print("=" * 60)

    driver = AsyncGraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    await driver.verify_connectivity()
    print("✓ Neo4j connected")

    # Get ALL chunks with substantial content
    async with driver.session() as session:
        result = await session.run("""
            MATCH (c:Chunk)
            WHERE size(c.content) > 30
            RETURN c.id AS chunk_id, c.content AS content
        """)
        chunks = await result.data()

    print(f"✓ Found {len(chunks)} chunks to process")
    print(f"✓ Concurrency: {CONCURRENCY}")
    print()

    # Clear existing Entity-Chunk relationships to avoid duplicates
    async with driver.session() as session:
        await session.run("MATCH (e:Entity)-[r:MENTIONS]->() DELETE r")
        await session.run("MATCH (e:Entity) SET e.label = ''")

    total_entities = 0
    total_rels = 0
    progress_lock = asyncio.Lock()
    batch_size = CONCURRENCY

    for batch_start in range(0, len(chunks), batch_size):
        batch_end = min(batch_start + batch_size, len(chunks))
        batch = chunks[batch_start:batch_end]
        i = batch_start + 1

        ents, rels = await process_batch(driver, batch, len(chunks), progress_lock)
        total_entities += ents
        total_rels += rels
        print(f"[{i}-{batch_end}/{len(chunks)}] +{ents} entities, +{rels} rels")

        if (batch_end // 100) % 5 == 0:
            await asyncio.sleep(0.5)

    print()
    print("=" * 60)
    print(f"  Done! Total: {total_entities} entities, {total_rels} relations")
    print("=" * 60)

    await driver.close()


if __name__ == "__main__":
    asyncio.run(main())