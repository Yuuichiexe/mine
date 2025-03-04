import os
from pyrogram import Client

API_ID = int(os.getenv("API_ID", "20222660"))
API_HASH = os.getenv("API_HASH", "5788f1f4a93f2de28835a0cf1b0ebae4")
BOT_TOKEN = os.getenv("BOT_TOKEN", "6694970760:AAFv6Zm9Av8HrY7JOTohg0E6c53Ar036eDc")

app = Client("word_guess_bot", bot_token=BOT_TOKEN, api_id=API_ID, api_hash=API_HASH)
