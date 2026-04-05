from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from core.config import Config

from core.models import Base


engine = create_async_engine(Config.DATABASE_URL)

async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def init_db():

    async with engine.begin() as conn:


        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncSession:

    async with async_session() as session:

        yield session

