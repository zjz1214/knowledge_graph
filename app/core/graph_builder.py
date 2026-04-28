import httpx
import json
from typing import Optional
from app.config import get_settings
from app.core.database import db
from app.core.embedding import embedding_model
from app.models.graph import Entity, Relationship, EntityType, RelationshipType
from app.models.note import Note

settings = get_settings()


class GraphBuilder:
    """Build knowledge graph from notes using Ollama LLM"""

    def __init__(self):
        self.ollama_url = settings.ollama_base_url
        self.embedding_model = embedding_model

    async def extract_entities(self, chunk_content: str) -> list[Entity]:
        """Extract entities from a chunk using local LLM"""
        prompt = f"""Extract entities from the following text.
Return a JSON array of entities with fields: id, label, type (concept/person/organization/topic/technique/tool/paper/other), description.

Text:
{chunk_content[:2000]}

Example output:
[
  {{"id": "entity_1", "label": "Machine Learning", "type": "concept", "description": "A field of AI"}}
]

Return ONLY the JSON array, no other text."""

        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": "qwen2.5:7b",  # or whatever local model
                    "prompt": prompt,
                    "stream": False
                }
            )
            response.raise_for_status()
            result = response.json()
            text = result.get("response", "")

        # Parse JSON
        try:
            # Try to extract JSON from response
            start = text.find("[")
            end = text.rfind("]") + 1
            if start >= 0 and end > start:
                entities_data = json.loads(text[start:end])
                return [Entity(**e) for e in entities_data]
        except json.JSONDecodeError:
            pass

        return []

    async def extract_relationships(self, entity1: Entity, entity2: Entity, context: str) -> Optional[Relationship]:
        """Extract relationship between two entities"""
        prompt = f"""Given two entities and their context, determine their relationship.
Entities: "{entity1.label}" and "{entity2.label}"
Context: {context[:500]}

Possible relationships: RELATES_TO, PART_OF, USES, DEFINES, CONTRADICTS, SUPPORTS, CITES, MENTIONS
Return ONLY a JSON object with fields: type, weight (0-1).
Example: {{"type": "USES", "weight": 0.8}}

If no meaningful relationship exists, return null."""

        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": "qwen2.5:7b",
                    "prompt": prompt,
                    "stream": False
                }
            )
            response.raise_for_status()
            result = response.json()
            text = result.get("response", "")

        try:
            # Find JSON in response
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                rel_data = json.loads(text[start:end])
                return Relationship(
                    source_id=entity1.id,
                    target_id=entity2.id,
                    type=RelationshipType(rel_data.get("type", "RELATES_TO")),
                    weight=rel_data.get("weight", 0.5)
                )
        except (json.JSONDecodeError, ValueError):
            pass

        return None

    async def build_graph(self, note: Note) -> tuple[list[Entity], list[Relationship]]:
        """Build graph from a note"""
        all_entities = []
        all_relationships = []

        for chunk in note.chunks:
            # Extract entities from chunk
            entities = await self.extract_entities(chunk.content)
            if not entities:
                continue

            # Generate embeddings for entities
            for entity in entities:
                entity.chunk_ids.append(chunk.id)
                try:
                    entity.embedding = await self.embedding_model.embed(entity.label)
                except Exception:
                    pass

            all_entities.extend(entities)

            # Extract relationships between entities in this chunk
            for i, e1 in enumerate(entities):
                for e2 in entities[i+1:]:
                    rel = await self.extract_relationships(e1, e2, chunk.content)
                    if rel:
                        all_relationships.append(rel)

        return all_entities, all_relationships

    async def store_in_neo4j(self, entities: list[Entity], relationships: list[Relationship]):
        """Store entities and relationships in Neo4j"""
        # Store entities
        for entity in entities:
            query = """
            MERGE (e:Entity {id: $id})
            SET e.label = $label,
                e.type = $type,
                e.description = $description,
                e.chunk_ids = $chunk_ids
            """
            await db.execute_write(query, {
                "id": entity.id,
                "label": entity.label,
                "type": entity.type.value,
                "description": entity.description,
                "chunk_ids": entity.chunk_ids
            })

            # Store embedding if available
            if entity.embedding:
                query = """
                MATCH (e:Entity {id: $id})
                SET e.embedding = $embedding
                """
                try:
                    await db.execute_write(query, {
                        "id": entity.id,
                        "embedding": entity.embedding
                    })
                except Exception:
                    pass

        # Store relationships
        for rel in relationships:
            query = """
            MATCH (s:Entity {id: $source_id})
            MATCH (t:Entity {id: $target_id})
            MERGE (s)-[r:RELATES_TO {type: $type}]->(t)
            SET r.weight = $weight
            """
            try:
                await db.execute_write(query, {
                    "source_id": rel.source_id,
                    "target_id": rel.target_id,
                    "type": rel.type.value,
                    "weight": rel.weight
                })
            except Exception:
                pass

    async def process_note(self, note: Note):
        """Full pipeline: extract, build, store"""
        entities, relationships = await self.build_graph(note)
        await self.store_in_neo4j(entities, relationships)
        return len(entities), len(relationships)


# Global instance
graph_builder = GraphBuilder()
