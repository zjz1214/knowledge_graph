"""
深度复习 API
预生成内容 + 节点管理
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


@router.get("/session")
async def get_deep_review_session(category: str = None, limit: int = 10):
    """
    获取预生成的复习会话
    """
    try:
        # 确保有足够的预生成内容
        await deep_review_engine.ensure_pregenerated(category, limit)

        # 获取预生成内容
        sessions = await deep_review_engine.get_pregenerated_session(category, limit)

        return {"entities": sessions}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate")
async def trigger_generation(category: str = None, count: int = 20):
    """
    手动触发预生成（通常由定时任务调用）
    """
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
    """删除复习内容"""
    try:
        success = await deep_review_engine.delete_review(review_id)
        return {"review_id": review_id, "success": success}
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
    """
    费曼反馈评估
    """
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
    """获取预生成统计"""
    try:
        total = await deep_review_engine.get_pregenerated_count()
        return {"total_pregenerated": total}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
