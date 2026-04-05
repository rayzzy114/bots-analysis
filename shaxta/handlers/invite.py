from aiogram import Router, F
from aiogram.types import InlineQuery, InlineQueryResultArticle, InputTextMessageContent, InlineKeyboardMarkup, InlineKeyboardButton

router = Router()

MESSAGE_TEXT = """Купить BTC.LTC.XMR легко и просто 👌

Мы работаем 24/7, круглосуточно.

Анонимно и безопасно."""

@router.inline_query(F.query.startswith("invite"))
async def handle_inline_query(inline_query: InlineQuery):
    try:
        bot_info = await inline_query.bot.get_me()
        bot_username = bot_info.username
        
        start_link = f"https://t.me/{bot_username}?start={inline_query.from_user.id}"
        
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Начать обмен", url=start_link)]
            ]
        )
        
        result = InlineQueryResultArticle(
            id="1",
            title="Отправить приглашение",
            description="Нажмите, чтобы отправить приглашение.",
            input_message_content=InputTextMessageContent(
                message_text=MESSAGE_TEXT
            ),
            reply_markup=keyboard,
            thumbnail_url="https://img.icons8.com/color/48/000000/bitcoin--v1.png"
        )
        
        await inline_query.answer(results=[result], cache_time=300)
        
    except Exception:
        await inline_query.answer(results=[], cache_time=1)