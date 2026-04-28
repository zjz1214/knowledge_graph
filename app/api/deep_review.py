"""
深度复习 API
预生成内容 + 节点管理 + 复习历史
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.review.deep_review import deep_review_engine

router = APIRouter(prefix="/deep-review", tags=["deep-review"])


class AnswerSubmission(BaseModel):
    review_id: str
    question_index: int
    answer: str


class EntityAction(BaseModel):
    entity_id: str


class RegenerateRequest(BaseModel):
    force: bool = False


@router.get("/session")
async def get_deep_review_session(category: str = None, limit: int = 10):
    """
    获取 active 状态的复习会话
    """
    try:
        await deep_review_engine.ensure_pregenerated(category, limit)
        sessions = await deep_review_engine.get_pregenerated_session(category, limit)
        return {"entities": sessions}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate")
async def trigger_generation(category: str = None, count: int = 20):
    """手动触发预生成"""
    try:
        await deep_review_engine.generate_batch(category, count)
        return {"status": "success", "message": f"已生成 {count} 条预复习内容"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/favorite/{review_id}")
async def toggle_favorite(review_id: str):
    """切换收藏状态"""
    try:
        is_favorited = await deep_review_engine.toggle_favorite(review_id)
        return {"review_id": review_id, "is_favorited": is_favorited}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/delete/{review_id}")
async def delete_review(review_id: str):
    """删除复习内容（兼容接口）"""
    try:
        success = await deep_review_engine.discard_review(review_id)
        return {"review_id": review_id, "success": success}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/keep/{review_id}")
async def keep_review(review_id: str):
    """标记为保留"""
    try:
        success = await deep_review_engine.keep_review(review_id)
        return {"review_id": review_id, "success": success}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/discard/{review_id}")
async def discard_review(review_id: str):
    """标记为丢弃"""
    try:
        success = await deep_review_engine.discard_review(review_id)
        return {"review_id": review_id, "success": success}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{review_id}/history")
async def get_review_history(review_id: str):
    """获取复习历史"""
    try:
        history = await deep_review_engine.get_review_history(review_id)
        return {"review_id": review_id, "history": history}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{review_id}/regenerate")
async def regenerate_review(review_id: str, req: RegenerateRequest = None):
    """重新生成问题"""
    try:
        force = req.force if req else False
        result = await deep_review_engine.regenerate_questions(review_id, force)
        if "error" in result and result.get("force_needed"):
            raise HTTPException(status_code=409, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/entity/{entity_id}")
async def get_entity_reviews(entity_id: str):
    """获取某实体的所有复习卡片"""
    try:
        reviews = await deep_review_engine.get_entity_reviews(entity_id)
        return {"entity_id": entity_id, "reviews": reviews}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/entity/delete")
async def delete_entity(action: EntityAction):
    """删除实体"""
    try:
        success = await deep_review_engine.delete_entity(action.entity_id)
        return {"entity_id": action.entity_id, "success": success}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/entity/favorite")
async def favorite_entity(action: EntityAction):
    """收藏实体"""
    try:
        await deep_review_engine.favorite_entity(action.entity_id)
        return {"entity_id": action.entity_id, "is_favorited": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/entity/unfavorite")
async def unfavorite_entity(action: EntityAction):
    """取消收藏实体"""
    try:
        await deep_review_engine.unfavorite_entity(action.entity_id)
        return {"entity_id": action.entity_id, "is_favorited": False}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/evaluate")
async def evaluate_answer(submission: AnswerSubmission):
    """费曼反馈评估"""
    try:
        result = await deep_review_engine.evaluate_answer(
            review_id=submission.review_id,
            question_index=submission.question_index,
            user_answer=submission.answer
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_stats():
    """获取复习统计"""
    try:
        total = await deep_review_engine.get_pregenerated_count()
        return {
            "total_pregenerated": total,
            "status": "active"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
