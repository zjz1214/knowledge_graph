#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

"""
完整的 Notion 导入脚本 - 获取页面标题和内容
"""

import asyncio
import hashlib
import json
import os
from pathlib import Path
from notion_client import AsyncClient
from neo4j import AsyncGraphDatabase
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("NOTION_API_KEY")
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")


def compute_id(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()[:12]


def extract_text(rich_text: list) -> str:
    """Extract plain text from Notion rich_text"""
    if not rich_text:
        return ''
    parts = []
    for t in rich_text:
        if t.get('type') == 'text':
            content = t.get('text', {}).get('content', '')
            ann = t.get('annotations', {})
            if ann.get('code'):
                content = f'`{content}`'
            if ann.get('bold'):
                content = f'**{content}**'
            if ann.get('italic'):
                content = f'*{content}*'
            parts.append(content)
        elif t.get('type') == 'mention':
            parts.append(t.get('plain_text', ''))
    return ''.join(parts)


def block_to_md(block: dict, depth: int = 0) -> str:
    """Convert a Notion block to markdown"""
    btype = block.get('type', '')
    content = block.get(btype, {})

    indent = '  ' * depth

    if btype == 'paragraph':
        text = extract_text(content.get('rich_text', []))
        return f'{text}\n' if text else '\n'
    elif btype == 'heading_1':
        return f'# {extract_text(content.get("rich_text", []))}\n'
    elif btype == 'heading_2':
        return f'## {extract_text(content.get("rich_text", []))}\n'
    elif btype == 'heading_3':
        return f'### {extract_text(content.get("rich_text", []))}\n'
    elif btype == 'bulleted_list_item':
        return f'{indent}- {extract_text(content.get("rich_text", []))}\n'
    elif btype == 'numbered_list_item':
        return f'{indent}1. {extract_text(content.get("rich_text", []))}\n'
    elif btype == 'to_do':
        checked = content.get('checked', False)
        text = extract_text(content.get('rich_text', []))
        return f'{indent}- [{"x" if checked else " "}] {text}\n'
    elif btype == 'code':
        lang = content.get('language', '')
        text = extract_text(content.get('rich_text', []))
        return f'```{lang}\n{text}\n```\n'
    elif btype == 'quote':
        return f'> {extract_text(content.get("rich_text", []))}\n'
    elif btype == 'callout':
        icon = content.get('icon') or {}
        emoji = icon.get('emoji', '💡') if isinstance(icon, dict) else '💡'
        return f'> {emoji} {extract_text(content.get("rich_text", []))}\n'
    elif btype == 'divider':
        return '---\n'
    elif btype == 'image':
        url = content.get('external', {}).get('url') or content.get('file', {}).get('url', '')
        caption = extract_text(content.get('caption', []))
        return f'![{caption}]({url})\n'
    elif btype == 'bookmark':
        url = content.get('url', '')
        return f'[{url}]({url})\n'
    return ''


async def get_page_blocks(page_id: str, notion: AsyncClient) -> list[dict]:
    """Get all blocks in a page"""
    blocks = []
    cursor = None

    while True:
        try:
            if cursor:
                resp = await notion.blocks.children.list(block_id=page_id, start_cursor=cursor)
            else:
                resp = await notion.blocks.children.list(block_id=page_id)

            blocks.extend(resp.get('results', []))
            cursor = resp.get('next_cursor')

            if not cursor:
                break

            await asyncio.sleep(0.3)  # Rate limiting

        except Exception as e:
            print(f'    [错误] 获取 blocks: {e}')
            break

    return blocks


async def get_page_title(page: dict, notion: AsyncClient) -> str:
    """Get page title from properties"""
    props = page.get('properties', {})
    for key in ['title', 'Name', '标题', 'name']:
        if key in props:
            val = props[key]
            if val.get('type') == 'title':
                return extract_text(val.get('title', []))
    return 'Untitled'


async def import_page_to_neo4j(page_id: str, notion: AsyncClient, driver):
    """Import a single Notion page to Neo4j with full content"""
    try:
        # Get page info
        page = await notion.pages.retrieve(page_id)
        title = await get_page_title(page, notion)
        tags = []

        # Get tags if available
        props = page.get('properties', {})
        for key, val in props.items():
            if val.get('type') == 'multi_select':
                tags = [item.get('name', '') for item in val.get('multi_select', [])]

        # Get blocks
        blocks = await get_page_blocks(page_id, notion)

        # Convert to markdown
        md_lines = [f'# {title}\n']
        for block in blocks:
            md = block_to_md(block)
            if md:
                md_lines.append(md)

        content = ''.join(md_lines)

        # Store in Neo4j
        async with driver.session() as session:
            note_id = compute_id(page_id)

            # Clear existing note and chunks
            await session.run("""
                MATCH (n:Note {id: $id})-[:CONTAINS]->(c:Chunk)
                DETACH DELETE c
                WITH n DELETE n
                """, id=note_id)

            # Create note
            await session.run("""
                CREATE (n:Note {
                    id: $id,
                    title: $title,
                    tags: $tags,
                    source: 'notion',
                    notion_id: $page_id,
                    created_at: datetime()
                })
                """, id=note_id, title=title, tags=tags, page_id=page_id)

            # Create chunk (the whole page as one chunk for now)
            chunk_id = f'{note_id}-0'
            await session.run("""
                MATCH (n:Note {id: $note_id})
                CREATE (c:Chunk {
                    id: $chunk_id,
                    content: $content
                })
                CREATE (n)-[:CONTAINS]->(c)
                """, note_id=note_id, chunk_id=chunk_id, content=content)

        return title, len(blocks)

    except Exception as e:
        print(f'    [错误] 导入页面 {page_id}: {e}')
        return None, 0


async def main():
    print('=' * 60)
    print('  Notion 完整导入')
    print('=' * 60)

    notion = AsyncClient(auth=TOKEN)
    driver = AsyncGraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    await driver.verify_connectivity()
    print('✓ 连接成功')

    # Search for all pages
    print('搜索 Notion 页面...')
    response = await notion.search(query='', filter={'value': 'page', 'property': 'object'}, page_size=100)
    pages = response.get('results', [])
    print(f'✓ 找到 {len(pages)} 个页面')

    if response.get('has_more'):
        cursor = response.get('next_cursor')
        while cursor:
            await asyncio.sleep(0.5)
            resp = await notion.search(query='', filter={'value': 'page', 'property': 'object'},
                                      page_size=100, start_cursor=cursor)
            pages.extend(resp.get('results', []))
            cursor = resp.get('next_cursor')
        print(f'✓ 共找到 {len(pages)} 个页面（全部）')

    print()
    print('开始导入...')

    imported = 0
    errors = 0

    for i, page in enumerate(pages, 1):
        page_id = page.get('id')
        title, block_count = await import_page_to_neo4j(page_id, notion, driver)

        if title:
            print(f'[{i}/{len(pages)}] ✓ {title} ({block_count} blocks)')
            imported += 1
        else:
            print(f'[{i}/{len(pages)}] ✗ 失败')
            errors += 1

        if i % 10 == 0:
            await asyncio.sleep(1)

    print()
    print('=' * 60)
    print(f'  完成！')
    print(f'  成功: {imported}')
    print(f'  失败: {errors}')
    print('=' * 60)

    await driver.close()


if __name__ == '__main__':
    asyncio.run(main())
