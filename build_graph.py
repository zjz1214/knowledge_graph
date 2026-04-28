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
import httpx
from neo4j import AsyncGraphDatabase
from dotenv import load_dotenv

load_dotenv()

NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "password"
OLLAMA_URL = "http://localhost:11434"
OLLAMA_MODEL = "llama3.2:latest"


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


async def extract_entities(chunk_content: str, chunk_id: str) -> tuple[list[dict], str]:
    """Extract entities from chunk using Ollama - 改进的详细提取"""
    # Detect category first
    category = detect_category(chunk_content)

    prompt = f"""你是一个知识图谱专家。从以下文本中提取所有重要的概念、术语、技术、方法等实体。

要求：
1. 尽可能提取细粒度的实体（不仅仅是大的概念）
2. 每个实体都要有明确的含义
3. 实体类型统一使用: concept, technique, tool, person, organization, method, metric, file, event

输出格式（严格JSON数组）：
[
  {{"id":"unique_id","label":"实体名称","type":"实体类型","description":"简短描述"}}
]

文本内容（来自知识库 chunk {chunk_id}）：
---
{chunk_content[:1500]}
---

直接返回JSON数组，不要任何解释。数量尽可能多。"""

    try:
        async with httpx.AsyncClient(timeout=180) as client:
            response = await client.post(
                f"{OLLAMA_URL}/api/generate",
                json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False}
            )
            result = response.json()
            text = result.get("response", "")
            entities = safe_json_parse(text)

            # Validate entities have required fields
            valid = []
            for e in entities:
                if isinstance(e, dict) and "label" in e:
                    label = e.get("label", "").strip()
                    if len(label) < 2:
                        continue
                    # Create unique id based on label
                    entity_id = compute_id(label) + "_" + e.get("type", "concept")[:4]
                    e["id"] = entity_id[:30]
                    e["type"] = e.get("type", "concept")
                    e["description"] = e.get("description", "")[:100]
                    e["category"] = category
                    valid.append(e)
            return valid, category
    except Exception as e:
        pass
    return [], category


async def extract_relationships(entities: list[dict], chunk_content: str) -> list[dict]:
    """Extract relationships between entities - 改进版"""
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
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                f"{OLLAMA_URL}/api/generate",
                json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False}
            )
            result = response.json()
            text = result.get("response", "")
            return safe_json_parse(text)
    except:
        pass
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


async def main():
    print("=" * 60)
    print("  Knowledge Graph Builder - Enhanced")
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
    print()

    # Clear existing Entity-Chunk relationships to avoid duplicates
    async with driver.session() as session:
        await session.run("MATCH (e:Entity)-[r:MENTIONS]->() DELETE r")
        # Keep entities but clear their labels to refresh
        await session.run("MATCH (e:Entity) SET e.label = ''")

    total_entities = 0
    total_rels = 0

    for i, chunk in enumerate(chunks, 1):
        chunk_id = chunk["chunk_id"]
        content = chunk["content"]

        if len(content) < 30:
            continue

        print(f"[{i}/{len(chunks)}] {chunk_id[:20]}...", end=" ", flush=True)

        ents, rels = await process_chunk(driver, chunk_id, content)
        total_entities += ents
        total_rels += rels
        print(f"+{ents} entities, +{rels} rels")

        if i % 20 == 0:
            await asyncio.sleep(1)

    print()
    print("=" * 60)
    print(f"  Done! Total: {total_entities} entities, {total_rels} relations")
    print("=" * 60)

    await driver.close()


if __name__ == "__main__":
    asyncio.run(main())