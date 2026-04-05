import json
from datetime import datetime
from pathlib import Path
import asyncio

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

router = Router()

USERS_FILE = Path("users.json")

def load_users():
    if not USERS_FILE.exists():
        return {}
    with open(USERS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_users(users_data):
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(users_data, f, ensure_ascii=False, indent=2)

def can_get_bonus_today(user_id):
    users = load_users()
    user_id_str = str(user_id)
    
    if user_id_str not in users:
        users[user_id_str] = {"last_bonus_date": None}
        save_users(users)
        return True
    
    last_bonus = users[user_id_str].get("last_bonus_date")
    
    if not last_bonus:
        return True
    
    try:
        last_date = datetime.fromisoformat(last_bonus)
        today = datetime.now().date()
        return last_date.date() < today
    except:
        return True

def update_bonus_date(user_id):
    users = load_users()
    user_id_str = str(user_id)
    
    if user_id_str not in users:
        users[user_id_str] = {}
    
    users[user_id_str]["last_bonus_date"] = datetime.now().isoformat()
    save_users(users)

async def daily_bonus(message: Message, edit: bool = False):
    user_id = message.from_user.id
    
    if not can_get_bonus_today(user_id):
        await message.answer("Вы уже участвовали в акции сегодня! Приходите завтра!❤️")
        return
    
    update_bonus_date(user_id)
    
    dice = await message.answer_dice()

    await asyncio.sleep(5)
    if dice.dice.value >= 4:
        msg = "🎉 Поздравляем! Ваш бонус будет применён к следующей сделке!"
    else:
        msg = "😔 К сожалению, сегодня вам не повезло. Попробуйте снова завтра!"
    
    await message.answer(msg)

@router.message(F.text == "🎁Ежедневный бонус🎁")
async def daily_bonus_handler(message: Message):
    kb = InlineKeyboardBuilder()
    kb.button(text="Бросить кость", callback_data="throw_dice")

    msg = ("Чтобы получить свой ежедневный бонус, брось кость!\n"
           "Приз действует на одну любую сделку (минимальной суммы нет) в рамках текущего дня!\n\n"
           
           "🎁 <b>Призы:</b>\n"
           "1️⃣ - 2 очка - никакого приза :(\n"
           "3️⃣ очка - 0,5% скидка на следующий обмен\n"
           "4️⃣ очка - 1,0% скидка на следующий обмен\n"
           "5️⃣ очков - 1,5% скидка на следующий обмен\n"
           "6️⃣ очков - 2,0% скидка на следующий обмен\n\n"
           
           "❗ 1% скидки подразумевает, что если, к примеру, комиссия 10%, то с 1% скидкой, комиссия будет 9%\n"
           "‼️ Бонус складывается с Вашей личной скидкой (на одну сделку)")
    
    await message.answer(msg, reply_markup=kb.as_markup())

@router.callback_query(F.data == "throw_dice")
async def throw_dice_callback(callback: CallbackQuery):
    await callback.answer()
    
    await daily_bonus(callback.message)