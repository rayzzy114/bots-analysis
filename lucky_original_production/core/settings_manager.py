from typing import Optional
from sqlalchemy import select
from core.database import async_session
from core.models import Setting

class SettingsManager:
    @staticmethod
    async def get_setting(key: str, default: Optional[str] = None) -> str:
        async with async_session() as session:
            result = await session.execute(select(Setting).where(Setting.key == key))
            setting = result.scalar_one_or_none()
            return setting.value if setting else (default or "")

    @staticmethod
    async def set_setting(key: str, value: str):
        async with async_session() as session:
            result = await session.execute(select(Setting).where(Setting.key == key))
            setting = result.scalar_one_or_none()
            if setting:
                setting.value = value
            else:
                session.add(Setting(key=key, value=value))
            await session.commit()

    @classmethod
    async def process_text(cls, text: str) -> str:
        async with async_session() as session:
            result = await session.execute(select(Setting))
            settings = result.scalars().all()
            for setting in settings:
                text = text.replace(f"{{{setting.key}}}", setting.value)
        return text
