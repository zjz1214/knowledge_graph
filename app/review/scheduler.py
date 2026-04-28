from datetime import date
from typing import Optional
from app.review.cards import card_manager
from app.models.note import Card, CardRating
from app.core.database import db


class ReviewScheduler:
    """
    Coordinates review sessions and manages card scheduling.
    Integrates graph centrality with FSRS for intelligent scheduling.
    """

    async def get_review_queue(self, limit: int = 20) -> dict:
        """
        Get today's review queue.
        Returns dict with 'due', 'new', and total counts.
        """
        due_cards = await card_manager.get_due_cards(limit)
        new_cards = await card_manager.get_new_cards(limit // 2)

        return {
            "due_cards": due_cards,
            "new_cards": new_cards,
            "due_count": len(due_cards),
            "new_count": len(new_cards),
            "total_count": len(due_cards) + len(new_cards)
        }

    async def get_review_stats(self) -> dict:
        """Get review statistics"""
        query = """
        MATCH (c:Card)
        RETURN
            count(c) AS total,
            sum(case when c.next_review <= date($today) then 1 else 0 end) AS due,
            sum(case when c.review_count = 0 then 1 else 0 end) AS new,
            avg(c.stability) AS avg_stability,
            avg(c.difficulty) AS avg_difficulty
        """
        results = await db.execute_query(query, {
            "today": date.today().isoformat()
        })

        if not results:
            return {
                "total": 0,
                "due": 0,
                "new": 0,
                "avg_stability": 0.0,
                "avg_difficulty": 2.5
            }

        r = results[0]
        return {
            "total": r.get("total", 0) or 0,
            "due": r.get("due", 0) or 0,
            "new": r.get("new", 0) or 0,
            "avg_stability": float(r.get("avg_stability", 0) or 0),
            "avg_difficulty": float(r.get("avg_difficulty", 2.5) or 2.5)
        }

    async def prioritize_by_graph_centrality(self, cards: list[Card], top_k: int = 5) -> list[Card]:
        """
        Reorder cards based on graph centrality.
        Cards linked to important entities (high PageRank) get priority.
        """
        # Get centrality scores from Neo4j
        centrality_query = """
        MATCH (e:Entity)
        WHERE e.id IN $entity_ids
        RETURN e.id AS entity_id, e.pagerank AS centrality
        ORDER BY e.pagerank DESC
        LIMIT $top_k
        """
        try:
            results = await db.execute_query(centrality_query, {
                "entity_ids": [c.entity_id for c in cards if c.entity_id],
                "top_k": top_k
            })
            if not results:
                return cards

            # Build priority map
            centrality_map = {r["entity_id"]: r["centrality"] for r in results}

            # Sort cards by centrality
            def centrality_sort_key(card: Card) -> float:
                return centrality_map.get(card.entity_id, 0.0)

            # Interleave with existing order
            cards_with_centrality = [(c, centrality_sort_key(c)) for c in cards]
            cards_with_centrality.sort(key=lambda x: -x[1])
            return [c for c, _ in cards_with_centrality]

        except Exception:
            return cards

    def generate_card_from_entity(self, entity_label: str, entity_description: str) -> Card:
        """Generate a review card from a graph entity"""
        return Card(
            question=f"什么是 {entity_label}？",
            answer=entity_description or f"{entity_label} 是一个概念。",
            tags=["auto-generated"],
            entity_id=None  # Will be set when linked
        )


# Global instance
scheduler = ReviewScheduler()
