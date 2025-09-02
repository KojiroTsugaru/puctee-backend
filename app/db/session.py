from ssl import create_default_context
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

# Ensure we use asyncpg driver for async operations
url = settings.DATABASE_URL
if url.startswith("postgresql://"):
    url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
if "localhost" in url:
    # Disable SSL for local
    connect_args = { "ssl": False }
else:
    # Remote has proper certificate validation
    ssl_context = create_default_context(cafile=settings.RDS_CA_BUNDLE)
    connect_args = { "ssl": ssl_context }

engine = create_async_engine(
    url,
    echo=False,
    future=True,
    connect_args=connect_args,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    pool_timeout=30,
    pool_recycle=3600
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