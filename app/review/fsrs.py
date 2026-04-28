"""
FSRS (Free Spaced Repetition Scheduler) Algorithm Implementation.

Based on the paper "A Mechanistic Model of Memory" and the Anki implementation.
Reference: https://github.com/open-spaced-repetition/fsrs
"""

import math
from datetime import datetime, date, timedelta
from dataclasses import dataclass
from app.models.note import Card, CardRating


@dataclass
class FSRSParams:
    """
    FSRS algorithm parameters.
    These control the forgetting curve and stability calculations.
    """
    # Request-retrieval stability (S) decay rate
    request_stability_decay: float = -0.5
    # Stability increase factor for successful retrieval
    request_stability_increase: float = 1.0

    # Difficulty factor (D) range
    min_difficulty: float = 1.0
    max_difficulty: float = 5.0

    # Initial values
    initial_stability: float = 1.0
    initial_difficulty: float = 2.5


# Default parameters
FSRS = FSRSParams()


def stability_after_rating(
    stability: float,
    difficulty: float,
    rating: CardRating
) -> float:
    """
    Calculate new stability (S) after a review.
    Higher stability = longer retention.
    """
    if stability <= 0:
        stability = FSRS.initial_stability

    # Compute retrieval stability adjustment
    if rating == CardRating.FORGOT:
        # Forgot: reset stability lower
        new_stability = stability * math.exp(FSRS.request_stability_decay)
        new_stability = max(0.1, new_stability)
    else:
        # Remembered: increase stability based on difficulty
        stability_increase = math.exp(rating.value - 2) * (1 - difficulty / FSRS.max_difficulty)
        new_stability = stability + stability_increase * FSRS.request_stability_increase

    return new_stability


def difficulty_after_rating(
    difficulty: float,
    rating: CardRating
) -> float:
    """
    Calculate new difficulty (D) after a review.
    Higher difficulty = harder to remember.
    """
    if rating == CardRating.FORGOT:
        # Forgot: increase difficulty
        new_difficulty = difficulty + 0.2
    elif rating == CardRating.EASY:
        # Easy: decrease difficulty slightly
        new_difficulty = difficulty - 0.15
    else:
        # Good/Hard: small adjustments
        new_difficulty = difficulty + (0.1 - (rating.value - 3) * 0.05)

    # Clamp to valid range
    return max(FSRS.min_difficulty, min(FSRS.max_difficulty, new_difficulty))


def interval_after_review(
    stability: float,
    difficulty: float,
    rating: CardRating,
    current_interval: int,
    review_count: int
) -> int:
    """
    Calculate next review interval in days.

    Uses the generalized forgetting curve model:
    R = exp(-t / S) where R is retention, t is time, S is stability
    """
    if rating == CardRating.FORGOT:
        # Reset to 1 day
        return 1

    # Target retention (higher for harder cards)
    target_retention = {
        CardRating.HARD: 0.85,
        CardRating.GOOD: 0.90,
        CardRating.EASY: 0.95
    }[rating]

    # Calculate interval using forgetting curve
    # t = -S * ln(R)
    stability_factor = stability / 10  # Scale factor
    interval = -stability_factor * math.log(target_retention)

    # Apply difficulty modifier
    difficulty_modifier = (difficulty - 1) / 4  # Normalize to 0-1
    interval = interval * (1 + difficulty_modifier * 0.5)

    # Minimum interval based on review count (spaced repetition)
    if review_count == 0:
        min_interval = 1
    elif review_count == 1:
        min_interval = 3
    else:
        min_interval = current_interval * 1.5

    interval = max(min_interval, interval)

    # Round and cap
    interval = max(1, min(365, round(interval)))

    return interval


def calculate_next_review(
    card: Card,
    rating: CardRating
) -> Card:
    """
    Update card state after a review.
    Returns updated card with new FSRS parameters.
    """
    # Calculate new stability and difficulty
    new_stability = stability_after_rating(card.stability, card.difficulty, rating)
    new_difficulty = difficulty_after_rating(card.difficulty, rating)

    # Update interval
    new_interval = interval_after_review(
        new_stability,
        new_difficulty,
        rating,
        card.interval,
        card.review_count
    )

    # Calculate next review date
    next_review_date = date.today() + timedelta(days=new_interval)

    # Update card
    card.stability = new_stability
    card.difficulty = new_difficulty
    card.interval = new_interval
    card.next_review = next_review_date
    card.review_count += 1
    card.last_reviewed = datetime.now()

    # Track lapses
    if rating == CardRating.FORGOT:
        card.lapses += 1

    return card


def get_retention(stability: float, days_elapsed: int) -> float:
    """
    Calculate expected retention after days_elapsed.
    R = exp(-t / S)
    """
    if stability <= 0:
        return 0.0
    return math.exp(-days_elapsed / stability)


def estimate_stability_from_interval(interval: int, difficulty: float) -> float:
    """
    Estimate stability from an interval.
    Useful when importing cards with existing intervals.
    """
    # Target retention of 0.9
    target_r = 0.9
    stability = -interval / math.log(target_r)
    # Adjust for difficulty
    stability *= (1 + (difficulty - 2.5) / 5)
    return max(0.1, stability)
