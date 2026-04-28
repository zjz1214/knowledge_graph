#!/usr/bin/env python3
"""
预生成深度复习内容脚本
可以配置为每日定时执行

用法:
    python generate_reviews.py              # 生成所有类别
    python generate_reviews.py --finance    # 只生成金融类
    python generate_reviews.py --tech --count 30  # 技术类30条
"""

import asyncio
import argparse
import sys
sys.stdout.reconfigure(encoding='utf-8')

from app.core.database import db
from app.review.deep_review import deep_review_engine


async def generate_for_category(category: str = None, count: int = 20):
    """为指定类别生成预复习内容"""
    print(f"开始为 {category or '全部'} 生成 {count} 条内容...")

    # 确保数据库连接
    await db.connect()

    try:
        # 检查现有数量
        existing = await deep_review_engine.get_pregenerated_count(category)
        print(f"当前已有: {existing} 条")

        if existing >= count:
            print("内容足够，无需生成")
            return

        # 生成新的
        need = count - existing
        await deep_review_engine.generate_batch(category, need)

        # 最终数量
        final = await deep_review_engine.get_pregenerated_count(category)
        print(f"生成完成，总计: {final} 条")

    finally:
        await db.close()


async def auto_generate_all():
    """自动生成所有类别的内容"""
    print("=" * 50)
    print("自动预生成深度复习内容")
    print("=" * 50)

    await db.connect()

    try:
        for cat in [None, 'finance', 'tech']:
            cat_name = cat or '全部'
            existing = await deep_review_engine.get_pregenerated_count(cat)
            print(f"\n[{cat_name}] 当前: {existing} 条")

            if existing < 15:
                await deep_review_engine.generate_batch(cat, 20 - existing)
            else:
                print(f"[{cat_name}] 数量足够，跳过")

    finally:
        await db.close()

    print("\n" + "=" * 50)
    print("预生成完成")


def main():
    parser = argparse.ArgumentParser(description='预生成深度复习内容')
    parser.add_argument('--category', choices=['finance', 'tech'], help='指定类别')
    parser.add_argument('--count', type=int, default=20, help='生成数量')
    parser.add_argument('--auto', action='store_true', help='自动生成所有类别')

    args = parser.parse_args()

    if args.auto:
        asyncio.run(auto_generate_all())
    else:
        asyncio.run(generate_for_category(args.category, args.count))


if __name__ == "__main__":
    main()
