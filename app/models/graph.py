from typing import Optional
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum


class EntityType(str, Enum):
    """Types of entities in the knowledge graph"""
    CONCEPT = "concept"
    PERSON = "person"
    ORGANIZATION = "organization"
    TOPIC = "topic"
    TECHNIQUE = "technique"
    TOOL = "tool"
    PAPER = "paper"
    OTHER = "other"


class RelationshipType(str, Enum):
    """Types of relationships between entities"""
    RELATES_TO = "RELATES_TO"
    PART_OF = "PART_OF"
    USES = "USES"
    DEFINES = "DEFINES"
    CONTRADICTS = "CONTRADICTS"
    SUPPORTS = "SUPPORTS"
    CITES = "CITES"
    MENTIONS = "MENTIONS"


class Entity(BaseModel):
    """An entity in the knowledge graph"""
    id: str
    label: str
    type: EntityType = EntityType.CONCEPT
    description: str = ""
    chunk_ids: list[str] = Field(default_factory=list)
    embedding: Optional[list[float]] = None
    properties: dict = Field(default_factory=dict)


class Relationship(BaseModel):
    """A relationship between two entities"""
    source_id: str
    target_id: str
    type: RelationshipType = RelationshipType.RELATES_TO
    weight: float = 1.0
    properties: dict = Field(default_factory=dict)


class GraphState(BaseModel):
    """Full graph state for a query"""
    entities: list[Entity] = Field(default_factory=list)
    relationships: list[Relationship] = Field(default_factory=list)
    communities: list[list[str]] = Field(default_factory=list)  # Entity IDs per community


class Chunk(BaseModel):
    """A content chunk linked to entities"""
    id: str
    content: str
    metadata: dict = Field(default_factory=dict)
    entity_ids: list[str] = Field(default_factory=list)
