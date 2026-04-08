from aiogram import Bot, Dispatcher
from aiogram.contrib.fsm_storage.memory import MemoryStorage

from config import *
from database import DataBase

storage = MemoryStorage()
bot = Bot(token, parse_mode='HTML')
dp = Dispatcher(bot, storage=storage)
db = DataBase('database.db')
