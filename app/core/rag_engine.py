import httpx
from typing import Optional
from app.config import get_settings
from app.core.database import db
from app.core.embedding import embedding_model

settings = get_settings()

TOKEN_PLAN_BASE = "https://token-plan-cn.xiaomimimo.com/v1"
TOKEN_PLAN_KEY = "tp-clupk2hrhxfh411yeo7kk22o4mxbnqzgi5avazgs273y7gc8"


class MiniMaxLLM:
    """token-plan LLM wrapper"""

    async def generate(self, prompt: str, system_prompt: str = None) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                f"{TOKEN_PLAN_BASE}/chat/completions",
                headers={"Authorization": f"Bearer {TOKEN_PLAN_KEY}"},
                json={"model": "mimo-v2.5-pro", "messages": messages, "max_tokens": 2048}
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]


class RAGEngine:
    """
    GraphRAG engine with dual model architecture:
    - Ollama (local) for embedding + local search
    - MiniMax API for generation
    """

    def __init__(self):
        self.embedding_model = embedding_model
        self.llm = MiniMaxLLM()

    async def local_search(self, query: str, top_k: int = 5) -> list[dict]:
        """
        Local search: vector similarity + graph neighborhood expansion.
        Returns relevant context chunks with graph relationships.
        """
        # Get query embedding
        query_embedding = await self.embedding_model.embed(query)

        # Find similar entities via vector search
        # Neo4j vector search (if plugin available)
        search_query = """
        MATCH (e:Entity)
        WHERE e.embedding IS NOT NULL
        WITH e, reduce(dot = 0.0, i IN range(0, size($query_embedding)-1) | dot + e.embedding[i] * $query_embedding[i]) AS similarity
        ORDER BY similarity DESC
        LIMIT $top_k
        RETURN e.id AS id, e.label AS label, e.description AS description, e.type AS type
        """
        try:
            results = await db.execute_query(search_query, {
                "query_embedding": query_embedding,
                "top_k": top_k
            })
            entities = results if results else []
        except Exception:
            # Fallback: text search
            search_query = """
            MATCH (e:Entity)
            WHERE e.label CONTAINS $query OR e.description CONTAINS $query
            LIMIT $top_k
            RETURN e.id AS id, e.label AS label, e.description AS description, e.type AS type
            """
            entities = await db.execute_query(search_query, {
                "query": query,
                "top_k": top_k
            }) or []

        # Expand to neighbors (1-2 hops)
        context_chunks = []
        for entity in entities[:3]:  # Top 3 entities
            neighbor_query = """
            MATCH (e:Entity {id: $id})-[r]-(neighbor)
            RETURN e.id AS entity_id, e.label AS entity_label,
                   neighbor.id AS neighbor_id, neighbor.label AS neighbor_label,
                   type(r) AS relationship
            UNION
            MATCH (e:Entity {id: $id})-[r]->(neighbor)
            RETURN e.id AS entity_id, e.label AS entity_label,
                   neighbor.id AS neighbor_id, neighbor.label AS neighbor_label,
                   type(r) AS relationship
            """
            try:
                neighbors = await db.execute_query(neighbor_query, {"id": entity["id"]}) or []
                for n in neighbors:
                    context_chunks.append({
                        "entity": entity,
                        "neighbor": n,
                        "relationship": n.get("relationship", "RELATES_TO")
                    })
            except Exception:
                pass

        return context_chunks

    async def global_search(self, query: str) -> str:
        """
        Global search: community-level aggregation.
        Detects communities and generates summary.
        """
        # Community detection (Leiden algorithm via Neo4j GDS)
        community_query = """
        CALL gds.graph.project('knowledge_graph', 'Entity', 'RELATES_TO')
        YIELD graphName
        CALL gds.leiden.write('knowledge_graph', {writeProperty: 'community'})
        YIELD communityCount
        RETURN communityCount
        """
        try:
            await db.execute_query(community_query)
        except Exception:
            pass  # GDS plugin may not be available

        # Get community summaries
        summary_query = """
        MATCH (e:Entity)
        WHERE e.community IS NOT NULL
        WITH e.community AS community, collect(e.label) AS entities
        RETURN community, entities
        ORDER BY size(entities) DESC
        LIMIT 10
        """
        try:
            communities = await db.execute_query(summary_query) or []
        except Exception:
            communities = []

        # Generate response based on communities
        context = "\n".join([
            f"Community {c['community']}: {', '.join(c['entities'][:10])}"
            for c in communities
        ])

        prompt = f"""Based on the following knowledge graph communities, answer the query.

Query: {query}

Knowledge Graph Communities:
{context}

Provide a comprehensive answer synthesizing information across these communities."""

        return await self.llm.generate(prompt, system_prompt="You are a helpful research assistant.")

    async def answer(self, query: str, search_mode: str = "local") -> str:
        """
        Answer a query using GraphRAG.
        Modes: "local" (focused), "global" (broad synthesis)
        """
        if search_mode == "global":
            return await self.global_search(query)

        # Local search
        context_results = await self.local_search(query)

        if not context_results:
            return "I couldn't find relevant information in the knowledge base."

        # Build context for LLM
        context_parts = []
        for result in context_results:
            entity = result.get("entity", {})
            neighbor = result.get("neighbor", {})
            rel = result.get("relationship", "RELATES_TO")
            context_parts.append(
                f"- {entity.get('label', '')} ({rel}) {neighbor.get('neighbor_label', '')}"
            )

        context = "\n".join(context_parts)

        prompt = f"""Based on the following retrieved context from a knowledge graph, answer the query.

Query: {query}

Retrieved Context:
{context}

If the context is insufficient, say so. Otherwise, provide a clear answer citing the relationships found."""

        return await self.llm.generate(prompt, system_prompt="You are a helpful research assistant with access to a knowledge graph.")


# Global instance
rag_engine = RAGEngine()
