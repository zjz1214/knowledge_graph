from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.review.cards import card_manager
from app.review.scheduler import scheduler
from app.models.note import Card, CardRating

router = APIRouter(prefix="/review", tags=["review"])


class ReviewRequest(BaseModel):
    card_id: str
    rating: int  # 1=forgot, 2=hard, 3=good, 4=easy


class CreateCardRequest(BaseModel):
    question: str
    answer: str
    tags: list[str] = []


@router.get("/queue")
async def get_review_queue(limit: int = 20):
    """Get today's review queue"""
    queue = await scheduler.get_review_queue(limit)
    return queue


@router.get("/stats")
async def get_review_stats():
    """Get review statistics"""
    stats = await scheduler.get_review_stats()
    return stats


@router.get("/{card_id}")
async def get_card(card_id: str):
    """Get a specific card"""
    card = await card_manager.get_card(card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    return card


@router.post("/")
async def create_card(request: CreateCardRequest):
    """Create a new review card"""
    card = Card(
        question=request.question,
        answer=request.answer,
        tags=request.tags
    )
    card = await card_manager.create_card(card)
    return card


@router.post("/submit")
async def submit_review(request: ReviewRequest):
    """Submit a review for a card"""
    card = await card_manager.get_card(request.card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    try:
        rating = CardRating(request.rating)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid rating (must be 1-4)")

    updated_card = await card_manager.review_card(card, rating)
    return {
        "card_id": updated_card.id,
        "new_interval": updated_card.interval,
        "next_review": updated_card.next_review.isoformat(),
        "stability": updated_card.stability,
        "difficulty": updated_card.difficulty
    }


@router.delete("/{card_id}")
async def delete_card(card_id: str):
    """Delete a card"""
    await card_manager.delete_card(card_id)
    return {"status": "deleted", "card_id": card_id}
