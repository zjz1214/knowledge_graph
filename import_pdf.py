#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

"""
PDF 批量导入脚本
递归扫描文件夹下所有 PDF，导入到 Neo4j

用法:
    python import_pdf.py data/pdfs/                          # 导入文件夹
    python import_pdf.py data/pdfs/ --category tech         # 指定分类
    python import_pdf.py data/pdfs/ --build-graph           # 同时构建图谱
"""

import sys
import os
import asyncio
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from app.core.pdf_parser import PDFParser, find_pdf_files
from app.core.database import db
from app.core.parser import compute_id
import hashlib
import re


def clean_text(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    text = re.sub(r'[\x80-\xff]{2,}', lambda m: '?' * len(m.group()), text)
    text = re.sub(r'[\ud800-\udfff]', '', text)
    return text.strip()


async def import_single_pdf(pdf_path: str, category: str = None, build_graph: bool = False):
    """导入单个 PDF 文件"""
    parser = PDFParser()
    chunks = parser.parse_file(pdf_path)

    if not chunks:
        print(f"  [跳过] 无法提取内容: {pdf_path}")
        return None

    # 生成标题
    title = os.path.splitext(os.path.basename(pdf_path))[0]
    note_id = compute_id(title + pdf_path)

    # 存储 Note
    await db.execute_write("""
        MERGE (n:Note {id: $note_id})
        SET n.title = $title,
            n.source = 'pdf',
            n.file_path = $file_path,
            n.category = $category,
            n.chunk_count = $chunk_count,
            n.created_at = datetime()
    """, {
        "note_id": note_id,
        "title": title,
        "file_path": pdf_path,
        "category": category or "other",
        "chunk_count": len(chunks)
    })

    # 存储 Chunks
    for chunk in chunks:
        chunk_id = hashlib.md5(f"{note_id}-{chunk['chunk_index']}".encode()).hexdigest()[:16]
        content = clean_text(chunk["text"])

        await db.execute_write("""
            MATCH (n:Note {id: $note_id})
            CREATE (c:Chunk {
                id: $chunk_id,
                content: $content,
                chunk_index: $chunk_index,
                page_start: $page_start,
                page_end: $page_end
            })
            CREATE (n)-[:CONTAINS]->(c)
        """, {
            "note_id": note_id,
            "chunk_id": chunk_id,
            "content": content[:5000],
            "chunk_index": chunk["chunk_index"],
            "page_start": chunk["page_start"],
            "page_end": chunk["page_end"]
        })

    return {"note_id": note_id, "chunks": len(chunks)}


async def main():
    parser = argparse.ArgumentParser(description="PDF 批量导入工具")
    parser.add_argument("path", help="PDF 文件或文件夹路径")
    parser.add_argument("--category", "-c", choices=["tech", "finance"], help="指定分类")
    parser.add_argument("--build-graph", "-g", action="store_true", help="导入后构建图谱")

    args = parser.parse_args()
    path = args.path

    await db.connect()
    print(f"Connected to Neo4j")

    if os.path.isfile(path):
        # 单个文件
        print(f"导入单个 PDF: {path}")
        result = await import_single_pdf(path, args.category, args.build_graph)
        if result:
            print(f"  ✓ {result['chunks']} chunks, note_id: {result['note_id']}")

    elif os.path.isdir(path):
        # 文件夹递归扫描
        pdfs = find_pdf_files(path)
        print(f"找到 {len(pdfs)} 个 PDF 文件")

        success = 0
        failed = 0

        for i, pdf_path in enumerate(pdfs, 1):
            rel = os.path.relpath(pdf_path, path)
            print(f"[{i}/{len(pdfs)}] {rel}", end=" ... ", flush=True)

            try:
                result = await import_single_pdf(pdf_path, args.category, args.build_graph)
                if result:
                    print(f"✓ {result['chunks']} chunks")
                    success += 1
                else:
                    failed += 1
            except Exception as e:
                print(f"✗ {e}")
                failed += 1

            if i % 10 == 0:
                await asyncio.sleep(0.5)

        print(f"\n完成: {success} 成功, {failed} 失败")

    else:
        print(f"路径不存在: {path}")

    await db.close()


if __name__ == "__main__":
    asyncio.run(main())