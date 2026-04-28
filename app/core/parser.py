import re
import hashlib
from pathlib import Path
from typing import Iterator
import frontmatter
from app.models.note import Note, NoteChunk


def compute_id(text: str) -> str:
    """Generate a deterministic ID from text"""
    return hashlib.md5(text.encode()).hexdigest()[:12]


def parse_markdown_file(file_path: Path) -> Note:
    """Parse a single Markdown file into a Note"""
    post = frontmatter.loads(file_path.read_text(encoding="utf-8"))

    # Extract metadata
    tags = post.metadata.get("tags", [])
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",")]

    title = post.metadata.get("title", file_path.stem)
    content = post.content

    # Generate ID from title
    note_id = compute_id(title)

    return Note(
        id=note_id,
        title=title,
        content=content,
        tags=tags,
        source="markdown"
    )


def chunk_by_headings(content: str, note_id: str) -> list[NoteChunk]:
    """
    Split note content into chunks by headings.
    Each H1/H2/H3 section becomes a chunk.
    """
    chunks = []
    lines = content.split("\n")

    current_heading = ""
    current_content_lines = []
    chunk_index = 0

    for line in lines:
        # Detect heading
        heading_match = re.match(r"^(#{1,3})\s+(.+)$", line)
        if heading_match:
            # Save previous chunk
            if current_content_lines:
                chunk_id = f"{note_id}-{chunk_index}"
                chunk_content = current_content_lines.join("\n").strip()
                if chunk_content:
                    chunks.append(NoteChunk(
                        id=chunk_id,
                        content=chunk_content,
                        metadata={"heading": current_heading}
                    ))
                chunk_index += 1

            current_heading = heading_match.group(2)
            current_content_lines = [line]
        else:
            current_content_lines.append(line)

    # Don't forget the last chunk
    if current_content_lines:
        chunk_id = f"{note_id}-{chunk_index}"
        chunk_content = "\n".join(current_content_lines).strip()
        if chunk_content:
            chunks.append(NoteChunk(
                id=chunk_id,
                content=chunk_content,
                metadata={"heading": current_heading}
            ))

    return chunks


def chunk_by_paragraphs(content: str, note_id: str, max_length: int = 500) -> list[NoteChunk]:
    """
    Split note content into chunks by paragraphs.
    Groups paragraphs until max_length is reached.
    """
    paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
    chunks = []
    current_chunk_lines = []
    current_length = 0
    chunk_index = 0

    for para in paragraphs:
        para_len = len(para)
        if current_length + para_len > max_length and current_chunk_lines:
            # Save current chunk
            chunk_id = f"{note_id}-{chunk_index}"
            chunk_content = "\n\n".join(current_chunk_lines)
            chunks.append(NoteChunk(
                id=chunk_id,
                content=chunk_content,
                metadata={}
            ))
            chunk_index += 1
            current_chunk_lines = []
            current_length = 0

        current_chunk_lines.append(para)
        current_length += para_len

    # Last chunk
    if current_chunk_lines:
        chunk_id = f"{note_id}-{chunk_index}"
        chunk_content = "\n\n".join(current_chunk_lines)
        chunks.append(NoteChunk(
            id=chunk_id,
            content=chunk_content,
            metadata={}
        ))

    return chunks


def load_notes_from_directory(directory: Path) -> Iterator[Note]:
    """Load all Markdown notes from a directory"""
    for md_file in directory.glob("**/*.md"):
        try:
            note = parse_markdown_file(md_file)
            note.chunks = chunk_by_headings(note.content, note.id)
            yield note
        except Exception as e:
            print(f"Error parsing {md_file}: {e}")
            continue
