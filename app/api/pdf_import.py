"""
PDF 导入 API
支持单个文件和批量文件夹导入
"""

import os
import hashlib
from fastapi import APIRouter, HTTPException, UploadFile, File, Query
from typing import Optional
from app.core.pdf_parser import PDFParser, find_pdf_files
from app.core.database import db
from app.core.parser import compute_id

router = APIRouter(prefix="/pdf", tags=["pdf"])


def _clean_text(text: str) -> str:
    """清洗文本"""
    import re
    if not text:
        return ""
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    text = re.sub(r'[\x80-\xff]{2,}', lambda m: '?' * len(m.group()), text)
    text = re.sub(r'[\ud800-\udfff]', '', text)
    return text.strip()


@router.post("/import")
async def import_pdf(
    file: UploadFile = File(...),
    category: Optional[str] = Query(None, description="分类: tech/finance"),
    build_graph: bool = Query(False, description="是否同步构建图谱")
):
    """
    导入单个 PDF 文件
    """
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="仅支持 PDF 文件")

    # 保存临时文件
    import tempfile
    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        parser = PDFParser()
        chunks = parser.parse_file(tmp_path)

        if not chunks:
            raise HTTPException(status_code=400, detail="PDF 无法提取文本内容")

        # 计算 PDF 标题
        title = os.path.splitext(file.filename)[0]
        if chunks and chunks[0].get("title"):
            title = chunks[0]["title"][:200]

        note_id = compute_id(title)

        # 存储 Note 节点
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
            "file_path": file.filename,
            "category": category or "other",
            "chunk_count": len(chunks)
        })

        # 存储 Chunk 节点
        for chunk in chunks:
            chunk_id = chunk.get("chunk_id", hashlib.md5(f"{note_id}-{chunk['chunk_index']}".encode()).hexdigest()[:16])
            content = _clean_text(chunk["text"])

            await db.execute_write("""
                MATCH (n:Note {id: $note_id})
                CREATE (c:Chunk {
                    id: $chunk_id,
                    content: $content,
                    chunk_index: $chunk_index,
                    page_start: $page_start,
                    page_end: $page_end,
                    frontmatter: $frontmatter
                })
                CREATE (n)-[:CONTAINS]->(c)
            """, {
                "note_id": note_id,
                "chunk_id": chunk_id,
                "content": content[:5000],  # 限制长度
                "chunk_index": chunk["chunk_index"],
                "page_start": chunk["page_start"],
                "page_end": chunk["page_end"],
                "frontmatter": f"title: {title}\nsource: pdf\npages: {chunk['page_start']}-{chunk['page_end']}"
            })

        return {
            "status": "success",
            "note_id": note_id,
            "title": title,
            "chunks": len(chunks),
            "build_graph": build_graph
        }

    finally:
        os.unlink(tmp_path)


@router.post("/import/directory")
async def import_pdf_directory(
    directory: str = Query(..., description="PDF 文件夹路径"),
    category: Optional[str] = Query(None),
    build_graph: bool = Query(False)
):
    """
    导入文件夹下所有 PDF 文件（递归遍历子文件夹）
    """
    if not os.path.isdir(directory):
        raise HTTPException(status_code=400, detail="文件夹路径不存在")

    pdf_files = find_pdf_files(directory)
    if not pdf_files:
        raise HTTPException(status_code=400, detail="文件夹中未找到 PDF 文件")

    results = []
    parser = PDFParser()

    for pdf_path in pdf_files:
        try:
            rel_path = os.path.relpath(pdf_path, directory)
            chunks = parser.parse_file(pdf_path)

            if not chunks:
                results.append({"file": rel_path, "status": "failed", "reason": "无法提取内容"})
                continue

            # 生成 note_id
            title = os.path.splitext(os.path.basename(pdf_path))[0]
            note_id = compute_id(title + rel_path)

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
                "file_path": rel_path,
                "category": category or "other",
                "chunk_count": len(chunks)
            })

            # 存储 Chunks
            for chunk in chunks:
                chunk_id = chunk.get("chunk_id", hashlib.md5(f"{note_id}-{chunk['chunk_index']}".encode()).hexdigest()[:16])
                content = _clean_text(chunk["text"])

                await db.execute_write("""
                    MATCH (n:Note {id: $note_id})
                    CREATE (c:Chunk {
                        id: $chunk_id,
                        content: $content,
                        chunk_index: $chunk_index,
                        page_start: $page_start,
                        page_end: $page_end,
                        frontmatter: $frontmatter
                    })
                    CREATE (n)-[:CONTAINS]->(c)
                """, {
                    "note_id": note_id,
                    "chunk_id": chunk_id,
                    "content": content[:5000],
                    "chunk_index": chunk["chunk_index"],
                    "page_start": chunk["page_start"],
                    "page_end": chunk["page_end"],
                    "frontmatter": f"title: {title}\nsource: pdf\nfile: {rel_path}\npages: {chunk['page_start']}-{chunk['page_end']}"
                })

            results.append({
                "file": rel_path,
                "status": "success",
                "note_id": note_id,
                "chunks": len(chunks)
            })

        except Exception as e:
            results.append({"file": rel_path, "status": "failed", "reason": str(e)})

    success_count = sum(1 for r in results if r["status"] == "success")
    return {
        "total": len(pdf_files),
        "success": success_count,
        "failed": len(pdf_files) - success_count,
        "results": results
    }


@router.get("/stats")
async def get_pdf_stats():
    """获取 PDF 导入统计"""
    try:
        results = await db.execute_query("""
            MATCH (n:Note {source: 'pdf'})
            RETURN count(n) AS total,
                   sum(n.chunk_count) AS total_chunks,
                   sum(CASE WHEN n.category = 'tech' THEN 1 ELSE 0 END) AS tech_count,
                   sum(CASE WHEN n.category = 'finance' THEN 1 ELSE 0 END) AS finance_count
        """)
        if not results:
            return {"total": 0, "total_chunks": 0, "tech_count": 0, "finance_count": 0}
        return results[0]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{note_id}")
async def get_pdf_note(note_id: str):
    """获取某 PDF 的详情和 chunks"""
    try:
        note = await db.execute_query("""
            MATCH (n:Note {id: $note_id, source: 'pdf'})
            RETURN n
        """, {"note_id": note_id})

        if not note:
            raise HTTPException(status_code=404, detail="PDF 不存在")

        chunks = await db.execute_query("""
            MATCH (n:Note {id: $note_id})-[:CONTAINS]->(c:Chunk)
            RETURN c.id AS id, c.content AS content, c.chunk_index AS index,
                   c.page_start AS page_start, c.page_end AS page_end
            ORDER BY c.chunk_index
        """, {"note_id": note_id})

        d = note[0]["n"]
        return {
            "id": d.get("id"),
            "title": d.get("title"),
            "source": d.get("source"),
            "file_path": d.get("file_path"),
            "category": d.get("category"),
            "chunk_count": d.get("chunk_count", 0),
            "chunks": [{
                "id": c["id"],
                "content": c["content"],
                "index": c["index"],
                "pages": f"{c['page_start']}-{c['page_end']}"
            } for c in chunks]
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))