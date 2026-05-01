#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""关系增强脚本：基于同笔记共现补充实体间关系"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

import asyncio
import logging
from neo4j import AsyncGraphDatabase
from collections import defaultdict

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "password"

CONCURRENCY = 20


async def process_note_cooccurrence(driver, note_id: str, note_title: str):
    """为同 note 下的实体对补充共现关系"""
    async with driver.session() as session:
        # 获取该 note 下所有 chunk 及其实体
        r = await session.run("""
            MATCH (n:Note {id: $note_id})-[:CONTAINS]->(c:Chunk)
            MATCH (e:Entity)-[:MENTIONS]->(c)
            WHERE e.label <> ""
            RETURN c.id as chunk_id, collect(DISTINCT e.id) as entity_ids
        """, note_id=note_id)
        chunk_entity_map = await r.data()

        if len(chunk_entity_map) < 2:
            return 0

        # 统计每对实体共现次数
        pair_count = defaultdict(int)
        for row in chunk_entity_map:
            eids = sorted(set(row["entity_ids"]))
            for i, e1 in enumerate(eids):
                for e2 in eids[i+1:]:
                    pair_count[(e1, e2)] += 1

        if not pair_count:
            return 0

        # 获取实体 label 用于调试
        all_eids = list(set(eid for pair in pair_count for eid in pair))
        r = await session.run(
            "MATCH (e:Entity) WHERE e.id IN $ids RETURN e.id as id, e.label as label",
            ids=all_eids
        )
        id_to_label = {row["id"]: row["label"] for row in await r.data()}

        new_rels = 0
        for (e1, e2), cnt in pair_count.items():
            if cnt < 2:  # 共现 >= 2 个 chunk 才建关系
                continue
            label1 = id_to_label.get(e1, "")
            label2 = id_to_label.get(e2, "")
            try:
                await session.run("""
                    MATCH (a:Entity {id: $e1}), (b:Entity {id: $e2})
                    MERGE (a)-[r:CO_OCCURS]->(b)
                    SET r.weight = $cnt,
                        r.note = $note_title,
                        r.source = 'cooccurrence'
                """, e1=e1, e2=e2, cnt=cnt, note_title=note_title)
                new_rels += 1
            except Exception:
                pass

        return new_rels


async def process_batch(driver, notes: list):
    tasks = []
    for note in notes:
        tasks.append(process_note_cooccurrence(driver, note["id"], note.get("title", "")))
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return sum(r if isinstance(r, int) else 0 for r in results)


async def main():
    print("=" * 60)
    print("  Relationship Enhancement - Co-occurrence")
    print("=" * 60)

    driver = AsyncGraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    await driver.verify_connectivity()
    print("✓ Neo4j connected")

    # 获取所有有 >=2 个 chunk 的 note
    async with driver.session() as session:
        r = await session.run("""
            MATCH (n:Note)-[:CONTAINS]->(c:Chunk)
            WITH n, count(c) as chunk_count
            WHERE chunk_count >= 2
            RETURN n.id as id, n.title as title, chunk_count
            ORDER BY chunk_count DESC
        """)
        notes = await r.data()

    print(f"✓ Found {len(notes)} notes with >=2 chunks to process")
    print(f"✓ Concurrency: {CONCURRENCY}")
    print()

    total_rels = 0
    for i in range(0, len(notes), CONCURRENCY):
        batch = notes[i:i+CONCURRENCY]
        rels = await process_batch(driver, batch)
        total_rels += rels
        print(f"[{i+1}-{min(i+CONCURRENCY, len(notes))}/{len(notes)}] +{rels} co-occurrence relationships")
        await asyncio.sleep(0.1)

    print()
    print("=" * 60)
    print(f"  Done! Total new relationships: {total_rels}")
    print("=" * 60)

    await driver.close()


if __name__ == "__main__":
    asyncio.run(main())
