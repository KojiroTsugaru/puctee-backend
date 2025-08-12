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
# Four levels up from __file__ is the project root
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from app.db.base import Base
from app.db.session import engine  # AsyncEngine
import app.models

async def reset_db():
    """
    ⚠️ Development/Test Environment Only ⚠️
    DROP → CREATE all tables.
    """
    async with engine.begin() as conn:
        # Drop the entire public schema
        await conn.execute(text("DROP SCHEMA public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))
        # Recreate all tables there
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Database has been reset!")

if __name__ == "__main__":
    # Load environment variables (load here if using dotenv etc.)
    # from dotenv import load_dotenv
    # load_dotenv()

    asyncio.run(reset_db())
