"""
节点管理 API
搜索、筛选、排序、分页
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from app.core.database import db

router = APIRouter(prefix="/entities", tags=["entities"])


@router.get("/")
async def list_entities(
    q: str = Query("", description="搜索关键词"),
    category: Optional[str] = Query(None, description="分类过滤: finance/tech/other"),
    favorited: bool = Query(False, description="只看收藏"),
    has_review: bool = Query(False, description="只看已有DeepReview的节点"),
    sort: str = Query("importance", description="排序: importance/connections/label"),
    order: str = Query("desc", description="顺序: asc/desc"),
    page: int = Query(1, ge=1, description="页码"),
    limit: int = Query(50, ge=1, le=200, description="每页条数"),
):
    """
    获取节点列表，支持搜索、筛选、排序、分页
    """
    try:
        # 构建 WHERE 条件
        conditions = []
        params = {}

        if q:
            conditions.append("(e.label CONTAINS $q OR e.description CONTAINS $q)")
            params["q"] = q

        if category:
            conditions.append("e.category = $category")
            params["category"] = category

        if favorited:
            conditions.append("e.is_favorited = true")

        where_clause = " AND ".join(conditions) if conditions else "true"

        # 排序字段映射
        sort_field_map = {
            "importance": "importance_score",
            "connections": "connections",
            "label": "e.label",
        }
        sort_field = sort_field_map.get(sort, "importance_score")
        sort_order = "DESC" if order == "desc" else "ASC"

        # 分页
        skip = (page - 1) * limit
        params["limit"] = limit
        params["skip"] = skip
        params["has_review"] = has_review

        # 查询总数
        count_query = f"""
        MATCH (e:Entity)
        WHERE {where_clause}
        RETURN count(e) AS total
        """
        count_results = await db.execute_query(count_query, params)
        total = count_results[0]["total"] if count_results else 0

        # 查询列表
        list_query = f"""
        MATCH (e:Entity)
        WHERE {where_clause}
        OPTIONAL MATCH (e)-[r]-()
        WITH e, count(r) AS connections
        OPTIONAL MATCH (d:DeepReview {{entity_id: e.id}})
        WITH e, connections, count(d) AS deep_review_count
        WHERE ($has_review = false OR deep_review_count > 0)
        RETURN e.id AS id,
               e.label AS label,
               e.type AS entity_type,
               e.category AS category,
               e.description AS description,
               e.is_favorited AS is_favorited,
               e.importance_score AS importance_score,
               connections,
               deep_review_count,
               ($has_review = false OR deep_review_count > 0) AS has_deep_review
        ORDER BY {sort_field} {sort_order}
        SKIP $skip
        LIMIT $limit
        """
        results = await db.execute_query(list_query, params) or []

        entities = []
        for r in results:
            entities.append({
                "id": r.get("id"),
                "label": r.get("label"),
                "type": r.get("entity_type"),
                "category": r.get("category"),
                "description": r.get("description") or "",
                "is_favorited": r.get("is_favorited", False),
                "importance_score": r.get("importance_score", 0),
                "connections": r.get("connections", 0),
                "deep_review_count": r.get("deep_review_count", 0),
                "has_deep_review": r.get("has_deep_review", False),
            })

        return {
            "total": total,
            "page": page,
            "pages": (total + limit - 1) // limit if total > 0 else 0,
            "entities": entities,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_entity_stats():
    """获取节点统计"""
    try:
        query = """
        MATCH (e:Entity)
        OPTIONAL MATCH (e)-[r]-()
        WITH e, count(r) AS connections
        RETURN count(e) AS total,
               sum(CASE WHEN e.category = 'tech' THEN 1 ELSE 0 END) AS tech_count,
               sum(CASE WHEN e.category = 'finance' THEN 1 ELSE 0 END) AS finance_count,
               sum(CASE WHEN e.is_favorited = true THEN 1 ELSE 0 END) AS favorited_count,
               max(connections) AS max_connections
        """
        results = await db.execute_query(query)
        if not results:
            return {"total": 0, "tech_count": 0, "finance_count": 0, "favorited_count": 0}
        return results[0]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
