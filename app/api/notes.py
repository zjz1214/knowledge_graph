from pathlib import Path
from fastapi import APIRouter, HTTPException
from app.core.parser import load_notes_from_directory, chunk_by_headings
from app.core.database import db

router = APIRouter(prefix="/notes", tags=["notes"])


@router.post("/import")
async def import_notes(directory: str = "data/notes"):
    """
    Import all Markdown notes from a directory.
    Simplified version: stores chunks without entity extraction.
    """
    notes_dir = Path(directory)
    if not notes_dir.exists():
        raise HTTPException(status_code=404, detail=f"Directory {directory} not found")

    imported = 0
    failed = 0
    total_chunks = 0

    for note in load_notes_from_directory(notes_dir):
        try:
            # Create Note node
            note_query = """
            MERGE (n:Note {id: $id})
            SET n.title = $title,
                n.tags = $tags,
                n.source = $source,
                n.created_at = datetime()
            """
            await db.execute_write(note_query, {
                "id": note.id,
                "title": note.title,
                "tags": note.tags,
                "source": note.source
            })

            # Create Chunk nodes
            for chunk in note.chunks:
                chunk_query = """
                MERGE (c:Chunk {id: $id})
                SET c.content = $content,
                    c.metadata = $metadata
                WITH c
                MATCH (n:Note {id: $note_id})
                MERGE (n)-[:CONTAINS]->(c)
                """
                await db.execute_write(chunk_query, {
                    "id": chunk.id,
                    "content": chunk.content,
                    "metadata": str(chunk.metadata),
                    "note_id": note.id
                })
                total_chunks += 1

            imported += 1
            print(f"Imported: {note.title} ({len(note.chunks)} chunks)")

        except Exception as e:
            failed += 1
            print(f"Failed to process note {note.id}: {e}")

    return {
        "imported": imported,
        "failed": failed,
        "chunks": total_chunks
    }


@router.get("/stats")
async def get_stats():
    """Get statistics about imported notes"""
    stats_query = """
    MATCH (n:Note)
    OPTIONAL MATCH (n)-[:CONTAINS]->(c:Chunk)
    RETURN count(n) AS note_count,
           count(c) AS chunk_count
    """
    try:
        results = await db.execute_query(stats_query)
        if results:
            return results[0]
    except Exception:
        pass

    return {"note_count": 0, "chunk_count": 0}


@router.get("/")
async def list_notes(limit: int = 50, offset: int = 0):
    """List all notes"""
    query = """
    MATCH (n:Note)
    OPTIONAL MATCH (n)-[:CONTAINS]->(c:Chunk)
    RETURN n.id AS id, n.title AS title, n.tags AS tags,
           count(c) AS chunk_count
    ORDER BY n.title
    SKIP $offset
    LIMIT $limit
    """
    results = await db.execute_query(query, {"offset": offset, "limit": limit})

    return {"notes": results, "offset": offset, "limit": limit}


@router.get("/{note_id}")
async def get_note(note_id: str):
    """Get a note and its chunks"""
    note_query = """
    MATCH (n:Note {id: $note_id})
    OPTIONAL MATCH (n)-[:CONTAINS]->(c:Chunk)
    RETURN n.id AS id, n.title AS title, n.tags AS tags,
           collect(c.id) AS chunk_ids
    """
    results = await db.execute_query(note_query, {"note_id": note_id})

    if not results:
        raise HTTPException(status_code=404, detail="Note not found")

    return results[0]
