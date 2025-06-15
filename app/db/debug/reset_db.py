#!/usr/bin/env python
import asyncio
from sqlalchemy import text
import os
import sys
from pathlib import Path


# └── <project_root>
#     └── app
#         └── db
#             └── debug
#                 └── reset_db.py  <- __file__
#
# __file__ の４つ上がプロジェクトルートになる
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from app.db.base import Base
from app.db.session import engine  # AsyncEngine
import app.models

async def reset_db():
    """
    ⚠️ 開発／テスト環境専用 ⚠️
    全テーブルを DROP → CREATE します。
    """
    async with engine.begin() as conn:
        # public スキーマごと消して
        await conn.execute(text("DROP SCHEMA public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))
        # そこに全テーブルを再作成
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Database has been reset!")

if __name__ == "__main__":
    # 環境変数読み込み（dotenv 等を使っている場合はここで読み込む）
    # from dotenv import load_dotenv
    # load_dotenv()

    asyncio.run(reset_db())
