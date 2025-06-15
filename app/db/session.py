from ssl import create_default_context
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

url = settings.DATABASE_URL
if "localhost" in url:
    # ローカルは SSL を無効化
    connect_args = { "ssl": False }
else:
    # リモートはちゃんと証明書検証あり
    ssl_context = create_default_context(cafile=settings.RDS_CA_BUNDLE)
    connect_args = { "ssl": ssl_context }

engine = create_async_engine(
    url,
    echo=True,
    future=True,
    connect_args=connect_args,
)

AsyncSessionLocal = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close() 