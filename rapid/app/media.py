from pathlib import Path

from aiogram.types import FSInputFile, Message


def asset_path(assets_dir: Path, name: str) -> Path:
    return assets_dir / name


async def send_screen(
    message: Message,
    assets_dir: Path,
    text: str,
    asset: str,
    keyboard=None,
) -> None:
    path = asset_path(assets_dir, asset)
    if path.exists():
        await message.answer_photo(photo=FSInputFile(path), caption=text, reply_markup=keyboard)
        return
    await message.answer(text, reply_markup=keyboard)
