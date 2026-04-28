from datetime import date
from typing import Optional
from app.core.database import db
from app.models.note import Card, CardRating
from app.review.fsrs import calculate_next_review, estimate_stability_from_interval


class CardManager:
    """Manage review cards in Neo4j"""

    async def create_card(self, card: Card) -> Card:
        """Create a new review card"""
        query = """
        CREATE (c:Card {
            id: randomUuid(),
            question: $question,
            answer: $answer,
            tags: $tags,
            entity_id: $entity_id,
            stability: $stability,
            difficulty: $difficulty,
            interval: $interval,
            next_review: $next_review,
            review_count: 0,
            lapses: 0,
            created_at: datetime(),
            last_reviewed: null
        })
        RETURN c.id AS id
        """
        result = await db.execute_write(query, {
            "question": card.question,
            "answer": card.answer,
            "tags": card.tags,
            "entity_id": card.entity_id,
            "stability": card.stability,
            "difficulty": card.difficulty,
            "interval": card.interval,
            "next_review": card.next_review.isoformat()
        })

        if result:
            card.id = result[0].get("id", "")
        return card

    async def get_card(self, card_id: str) -> Optional[Card]:
        """Get a card by ID"""
        query = """
        MATCH (c:Card {id: $id})
        RETURN c
        """
        results = await db.execute_query(query, {"id": card_id})
        if not results:
            return None

        data = results[0]["c"]
        return Card(
            id=data["id"],
            question=data["question"],
            answer=data["answer"],
            tags=data.get("tags", []),
            entity_id=data.get("entity_id"),
            stability=data.get("stability", 0.0),
            difficulty=data.get("difficulty", 2.5),
            interval=data.get("interval", 0),
            next_review=date.fromisoformat(data["next_review"]) if isinstance(data["next_review"], str) else data["next_review"],
            review_count=data.get("review_count", 0),
            lapses=data.get("lapses", 0)
        )

    async def update_card(self, card: Card) -> Card:
        """Update an existing card"""
        query = """
        MATCH (c:Card {id: $id})
        SET c.question = $question,
            c.answer = $answer,
            c.tags = $tags,
            c.entity_id = $entity_id,
            c.stability = $stability,
            c.difficulty = $difficulty,
            c.interval = $interval,
            c.next_review = $next_review,
            c.review_count = $review_count,
            c.lapses = $lapses,
            c.last_reviewed = $last_reviewed
        """
        await db.execute_write(query, {
            "id": card.id,
            "question": card.question,
            "answer": card.answer,
            "tags": card.tags,
            "entity_id": card.entity_id,
            "stability": card.stability,
            "difficulty": card.difficulty,
            "interval": card.interval,
            "next_review": card.next_review.isoformat(),
            "review_count": card.review_count,
            "lapses": card.lapses,
            "last_reviewed": card.last_reviewed.isoformat() if card.last_reviewed else None
        })
        return card

    async def review_card(self, card: Card, rating: CardRating) -> Card:
        """Review a card and update its FSRS state"""
        updated_card = calculate_next_review(card, rating)
        return await self.update_card(updated_card)

    async def delete_card(self, card_id: str) -> bool:
        """Delete a card"""
        query = """
        MATCH (c:Card {id: $id})
        DELETE c
        """
        await db.execute_write(query, {"id": card_id})
        return True

    async def get_due_cards(self, limit: int = 20) -> list[Card]:
        """Get cards due for review today"""
        query = """
        MATCH (c:Card)
        WHERE c.next_review <= date($today)
        RETURN c
        ORDER BY c.next_review, c.stability ASC
        LIMIT $limit
        """
        results = await db.execute_query(query, {
            "today": date.today().isoformat(),
            "limit": limit
        })

        cards = []
        for record in results:
            data = record["c"]
            cards.append(Card(
                id=data["id"],
                question=data["question"],
                answer=data["answer"],
                tags=data.get("tags", []),
                entity_id=data.get("entity_id"),
                stability=data.get("stability", 0.0),
                difficulty=data.get("difficulty", 2.5),
                interval=data.get("interval", 0),
                next_review=date.fromisoformat(data["next_review"]) if isinstance(data["next_review"], str) else data["next_review"],
                review_count=data.get("review_count", 0),
                lapses=data.get("lapses", 0)
            ))
        return cards

    async def get_new_cards(self, limit: int = 10) -> list[Card]:
        """Get new cards that haven't been reviewed yet"""
        query = """
        MATCH (c:Card)
        WHERE c.review_count = 0
        RETURN c
        LIMIT $limit
        """
        results = await db.execute_query(query, {"limit": limit})

        cards = []
        for record in results:
            data = record["c"]
            cards.append(Card(
                id=data["id"],
                question=data["question"],
                answer=data["answer"],
                tags=data.get("tags", []),
                entity_id=data.get("entity_id"),
                stability=data.get("stability", 0.0),
                difficulty=data.get("difficulty", 2.5),
                interval=data.get("interval", 0),
                next_review=date.fromisoformat(data["next_review"]) if isinstance(data["next_review"], str) else data["next_review"],
                review_count=0,
                lapses=0
            ))
        return cards


# Global instance
card_manager = CardManager()
