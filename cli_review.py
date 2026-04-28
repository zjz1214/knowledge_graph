#!/usr/bin/env python3
"""
CLI Review Script
打开终端运行 python cli_review.py 即可复习今日卡片
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from app.core.database import db
from app.review.scheduler import scheduler
from app.review.cards import card_manager
from app.models.note import CardRating


def print_card(card, index, total):
    """Pretty print a card"""
    print("=" * 60)
    print(f"卡片 {index}/{total}")
    print("=" * 60)
    print(f"[{', '.join(card.tags)}]")
    print()
    print(f"问题: {card.question}")
    print()
    print("答案提示: ", end="")
    input()  # Wait for Enter to reveal
    print(f"      {card.answer}")
    print()
    print("-" * 40)
    print("评分: [1] 忘记  [2] 模糊  [3] 记住  [4] 完全记住  [Q] 退出")
    print()


async def main():
    print("\n" + "=" * 60)
    print("  知识复习系统")
    print("=" * 60 + "\n")

    # Connect to database
    try:
        await db.connect()
        await db.init_indexes()
    except Exception as e:
        print(f"连接数据库失败: {e}")
        print("请确保 Neo4j 已启动 (docker-compose up -d)")
        return

    # Get review queue
    queue = await scheduler.get_review_queue(limit=20)

    if queue["total_count"] == 0:
        print("今日没有需要复习的卡片！")
        print("恭喜你完成了今天的复习任务。")
        return

    print(f"今日待复习: {queue['due_count']} 张到期 + {queue['new_count']} 张新卡片\n")

    all_cards = queue["due_cards"] + queue["new_cards"]
    reviewed = 0
    ratings_count = {1: 0, 2: 0, 3: 0, 4: 0}

    for i, card in enumerate(all_cards, 1):
        print_card(card, i, len(all_cards))

        while True:
            choice = input("选择: ").strip().lower()

            if choice == "q":
                print("\n退出复习。")
                print(f"本次复习: {reviewed}/{len(all_cards)} 张")
                await db.close()
                return

            try:
                rating = CardRating(int(choice))
            except (ValueError, KeyError):
                print("无效选择，请输入 1-4 或 Q")
                continue

            # Submit review
            await card_manager.review_card(card, rating)
            reviewed += 1
            ratings_count[rating.value] += 1

            # Show next review interval
            updated_card = await card_manager.get_card(card.id)
            print(f"  -> 下次复习: {updated_card.interval} 天后 ({updated_card.next_review})")
            print()
            break

    # Summary
    print("\n" + "=" * 60)
    print("  复习完成！")
    print("=" * 60)
    print(f"复习卡片数: {reviewed}")
    print(f"评级分布: 忘记 {ratings_count[1]}  模糊 {ratings_count[2]}  记住 {ratings_count[3]}  完全记住 {ratings_count[4]}")
    print()

    await db.close()


if __name__ == "__main__":
    asyncio.run(main())
