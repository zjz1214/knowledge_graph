"""
定时预生成任务
在后台运行，每日自动生成复习内容

用法:
    python schedule_review.py    # 启动定时任务
"""

import asyncio
import schedule
import time
import threading
import sys
sys.stdout.reconfigure(encoding='utf-8')

from app.core.database import db
from app.review.deep_review import deep_review_engine


async def daily_generation():
    """每日生成任务"""
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 开始每日预生成...")

    await db.connect()
    try:
        for cat in [None, 'finance', 'tech']:
            cat_name = cat or '全部'
            existing = await deep_review_engine.get_pregenerated_count(cat)
            print(f"  [{cat_name}] 当前: {existing} 条")

            if existing < 20:
                await deep_review_engine.generate_batch(cat, 25 - existing)
            else:
                print(f"  [{cat_name}] 数量足够，跳过")

        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 每日预生成完成")
    finally:
        await db.close()


def run_async(coro):
    """在新线程中运行 async 函数"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def job():
    """定时任务入口"""
    run_async(daily_generation())


def main():
    print("=" * 50)
    print("深度复习定时预生成服务")
    print("=" * 50)

    # 立即执行一次
    print("\n立即执行一次预生成...")
    job()

    # 设置每日定时任务
    # 每天早上 8:00 执行
    schedule.every().day.at("08:00").do(job)

    # 每天晚上 20:00 追加一次
    schedule.every().day.at("20:00").do(job)

    print("\n定时任务已设置:")
    print("  - 每天 08:00 自动预生成")
    print("  - 每天 20:00 补充预生成")
    print("\n按 Ctrl+C 退出")

    # 运行定时任务
    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    main()
