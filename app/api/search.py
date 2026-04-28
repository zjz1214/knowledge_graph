from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.core.rag_engine import rag_engine
from app.core.database import db

router = APIRouter(prefix="/search", tags=["search"])


class SearchRequest(BaseModel):
    query: str
    mode: str = "local"  # "local" or "global"


class RAGRequest(BaseModel):
    query: str
    mode: str = "local"


@router.post("/rag")
async def rag_search(request: RAGRequest):
    """
    GraphRAG search endpoint.
    mode: "local" for focused retrieval, "global" for broad synthesis.
    """
    try:
        answer = await rag_engine.answer(request.query, search_mode=request.mode)
        return {
            "query": request.query,
            "mode": request.mode,
            "answer": answer
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/local/{entity_id}")
async def get_entity_neighbors(entity_id: str, depth: int = 2):
    """Get entity and its neighbors in the graph"""
    query = f"""
    MATCH path = (e:Entity {{id: $id}})-[r*1..{depth}]-(neighbor)
    RETURN e AS center,
           [node IN nodes(path) | {{id: node.id, label: node.label, type: node.type}}] AS nodes,
           [rel IN relationships(path) | {{type: type(rel), weight: rel.weight}}] AS relationships
    """
    results = await db.execute_query(query, {"id": entity_id})

    if not results:
        raise HTTPException(status_code=404, detail="Entity not found")

    return {
        "center": results[0]["center"],
        "paths": [{
            "nodes": r["nodes"],
            "relationships": r["relationships"]
        } for r in results]
    }


@router.get("/entity/{entity_id}")
async def get_entity_details(entity_id: str):
    """Get detailed info about an entity including its description and related chunks"""
    # Get entity
    entity_query = """
    MATCH (e:Entity {id: $id})
    RETURN e.id AS id, e.label AS label, e.type AS type, e.description AS description
    """
    entity_results = await db.execute_query(entity_query, {"id": entity_id})

    if not entity_results:
        raise HTTPException(status_code=404, detail="Entity not found")

    entity = entity_results[0]

    # Get chunks this entity mentions
    chunks_query = """
    MATCH (e:Entity {id: $id})-[r:MENTIONS]->(c:Chunk)
    RETURN c.id AS chunk_id, c.content AS content
    LIMIT 5
    """
    chunks = await db.execute_query(chunks_query, {"id": entity_id}) or []

    # Get neighbors
    neighbors_query = """
    MATCH (e:Entity {id: $id})-[r]-(neighbor)
    WHERE size(neighbor.label) > 0
    RETURN neighbor.id AS id, neighbor.label AS label, neighbor.type AS type, type(r) AS rel_type
    LIMIT 20
    """
    neighbors = await db.execute_query(neighbors_query, {"id": entity_id}) or []

    return {
        "entity": entity,
        "chunks": [{"chunk_id": c["chunk_id"], "preview": c["content"][:200] if c["content"] else ""} for c in chunks],
        "neighbors": neighbors
    }


@router.get("/graph/sample")
async def get_graph_sample(limit: int = 200, category: str = None):
    """
    Get sample graph data for visualization.
    Returns entities and their relationships.
    Filter by category: "finance", "tech", or None for all.
    """
    if category and category in ['finance', 'tech']:
        query = """
        MATCH (e:Entity)
        WHERE size(e.label) > 1 AND e.category = $category
        OPTIONAL MATCH (e)-[r]-(e2)
        WHERE size(e2.label) > 1 AND e2.category = $category
        RETURN e.id AS id, e.label AS label, e.type AS type,
               collect(DISTINCT {id: e2.id, label: e2.label, type: e2.type}) AS neighbors
        LIMIT $limit
        """
    else:
        query = """
        MATCH (e:Entity)
        WHERE size(e.label) > 1
        OPTIONAL MATCH (e)-[r]-(e2)
        WHERE size(e2.label) > 1
        RETURN e.id AS id, e.label AS label, e.type AS type,
               collect(DISTINCT {id: e2.id, label: e2.label, type: e2.type}) AS neighbors
        LIMIT $limit
        """
    try:
        if category and category in ['finance', 'tech']:
            results = await db.execute_query(query, {"limit": limit, "category": category}) or []
        else:
            results = await db.execute_query(query, {"limit": limit}) or []
    except Exception:
        return {"nodes": [], "links": []}

    # Build nodes and links
    node_map = {}
    links = []
    nodes = []

    for r in results:
        node_id = r.get("id", "")
        label = r.get("label", "")
        ntype = r.get("type", "concept")
        neighbors = r.get("neighbors") or []

        if node_id and label:
            if node_id not in node_map:
                node_map[node_id] = {"id": node_id, "label": label, "type": ntype}

            for n in neighbors:
                neighbor_id = n.get("id", "")
                neighbor_label = n.get("label", "")
                if neighbor_id and neighbor_label and neighbor_id != node_id:
                    if neighbor_id not in node_map:
                        node_map[neighbor_id] = {"id": neighbor_id, "label": neighbor_label, "type": n.get("type", "concept")}
                    links.append({"source": node_id, "target": neighbor_id})

    return {
        "nodes": list(node_map.values()),
        "links": links
    }


@router.get("/communities")
async def get_communities():
    """Get knowledge graph communities"""
    query = """
    MATCH (e:Entity)
    WHERE e.community IS NOT NULL
    WITH e.community AS community, collect(e.label) AS entities, count(*) AS size
    RETURN community, entities, size
    ORDER BY size DESC
    """
    try:
        results = await db.execute_query(query)
        return {"communities": results}
    except Exception:
        return {"communities": [], "note": "Community detection requires GDS plugin"}
