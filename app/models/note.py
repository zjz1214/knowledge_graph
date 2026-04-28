from datetime import datetime, date
from typing import Optional
from pydantic import BaseModel, Field
from enum import Enum


class CardRating(int, Enum):
    """FSRS rating scale"""
    FORGOT = 1      # 忘记
    HARD = 2        # 模糊
    GOOD = 3        # 记住
    EASY = 4        # 完全记住


class NoteChunk(BaseModel):
    """A chunk of a note (section or paragraph)"""
    id: str
    content: str
    metadata: dict = Field(default_factory=dict)
    embedding: Optional[list[float]] = None


class Card(BaseModel):
    """Review card with FSRS state"""
    id: str = ""
    question: str
    answer: str
    tags: list[str] = Field(default_factory=list)
    entity_id: Optional[str] = None  # Link to graph entity

    # FSRS state
    stability: float = 0.0       # Stability (S)
    difficulty: float = 2.5      # Difficulty (D), 0-5 scale
    interval: int = 0            # Current interval in days
    next_review: date = Field(default_factory=date.today)
    review_count: int = 0
    lapses: int = 0              # Number of times forgotten

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.now)
    last_reviewed: Optional[datetime] = None


class Note(BaseModel):
    """A source note"""
    id: str
    title: str
    content: str
    tags: list[str] = Field(default_factory=list)
    source: str = "markdown"  # "notion" or "markdown"
    chunks: list[NoteChunk] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
