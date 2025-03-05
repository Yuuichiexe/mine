import random
import requests
from pyrogram import Client, filters
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from database import get_user_points, update_user_points
from mine import app
from mine.game import challenger_data
# Store ongoing challenges


# Fallback words if API fails
fallback_words = {
    4: ["play", "word", "game", "chat"],
    5: ["guess", "brain", "smart", "think"],
    6: ["random", "puzzle", "letter", "breeze"],
    7: ["amazing", "thought", "journey", "fantasy"]
}

# Fetch words from Datamuse API
def fetch_words(word_length):
    try:
        response = requests.get(f"https://api.datamuse.com/words?sp={'?' * word_length}&max=1000", timeout=5)
        response.raise_for_status()
        words = [word["word"] for word in response.json()]
        return words if words else fallback_words[word_length]
    except requests.RequestException:
        return fallback_words[word_length]

# Preload words
word_lists = {length: fetch_words(length) for length in fallback_words}

def get_random_word(word_length):
    return random.choice(word_lists[word_length])


@app.on_message(filters.command("challenge"))
async def handle_challenge(client, message):
    args = message.text.split()

    if len(args) != 3 or not args[2].isdigit():
        await message.reply("⚠️ Usage: `/challenge @username bet_amount`", quote=True)
        return

    bet_amount = int(args[2])
    challenger_id = message.from_user.id
    opponent_id = None

    # Extract opponent from reply or mention
    if message.reply_to_message:  
        opponent_id = message.reply_to_message.from_user.id
    else:
        entities = message.entities or []
        mentioned_usernames = [entity for entity in entities if entity.type == MessageEntityType.MENTION]
        if mentioned_usernames:
            mentioned_username = args[1]  
            try:
                opponent = await client.get_users(mentioned_username)
                opponent_id = opponent.id
            except Exception:
                await message.reply("⚠️ Invalid username! Make sure the user exists and is not private.", quote=True)
                return
        else:
            await message.reply("⚠️ Please reply to a user or tag a valid username!", quote=True)
            return

    if opponent_id == challenger_id:
        await message.reply("⚠️ You cannot challenge yourself!", quote=True)
        return

    challenger_points = get_user_points(challenger_id)
    opponent_points = get_user_points(opponent_id)

    if challenger_points < bet_amount:
        await message.reply("❌ You don't have enough points!", quote=True)
        return

    if opponent_points < bet_amount:
        await message.reply(f"❌ The opponent doesn't have enough points!", quote=True)
        return

    # Store challenge details
    challenger_data[challenger_id] = {
        "opponent_id": opponent_id,
        "bet_amount": bet_amount
    }

    buttons = [
        [InlineKeyboardButton("4 Letters", callback_data=f"challenge_length_4_{challenger_id}")],
        [InlineKeyboardButton("5 Letters", callback_data=f"challenge_length_5_{challenger_id}")],
        [InlineKeyboardButton("6 Letters", callback_data=f"challenge_length_6_{challenger_id}")],
        [InlineKeyboardButton("7 Letters", callback_data=f"challenge_length_7_{challenger_id}")],
    ]

    await message.reply(
        f"🎯 **{message.from_user.mention} has challenged [{opponent_id}](tg://user?id={opponent_id})!**\n"
        f"💰 **Bet Amount:** `{bet_amount}` points\n\n"
        "🔢 *Challenger, select a word length:*",
        reply_markup=InlineKeyboardMarkup(buttons),
        quote=True
    )


@app.on_callback_query(filters.regex("^challenge_length_"))
async def select_challenge_length(client, callback_query):
    data = callback_query.data.split("_")
    word_length = int(data[2])
    challenger_id = int(data[3])

    if challenger_id != callback_query.from_user.id:
        await callback_query.answer("⚠️ Only the challenger can select the word length!", show_alert=True)
        return

    if challenger_id not in challenger_data:
        await callback_query.answer("⚠️ Challenge not found!", show_alert=True)
        return

    challenger_data[challenger_id]["word_length"] = word_length
    opponent_id = challenger_data[challenger_id]["opponent_id"]

    buttons = [
        [InlineKeyboardButton("✅ Accept", callback_data=f"accept_{challenger_id}")],
        [InlineKeyboardButton("❌ Decline", callback_data=f"decline_{challenger_id}")],
    ]

    await callback_query.message.edit_text(
        f"✅ **{callback_query.from_user.mention} selected a {word_length}-letter word!**\n"
        f"👤 **[{opponent_id}](tg://user?id={opponent_id})**, do you accept?",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

@app.on_callback_query(filters.regex("^accept_"))
async def accept_challenge(client, callback_query):
    opponent_id = callback_query.from_user.id
    challenger_id = int(callback_query.data.split("_")[1])

    if challenger_id not in challenger_data or challenger_data[challenger_id]["opponent_id"] != opponent_id:
        await callback_query.answer("⚠️ This challenge is not for you!", show_alert=True)
        return

    game_data = challenger_data[challenger_id]
    word_length = game_data["word_length"]
    word = get_random_word(word_length)
    bet_amount = game_data["bet_amount"]

    # Deduct bet from both players initially
    update_user_points(challenger_id, -bet_amount)
    update_user_points(opponent_id, -bet_amount)

    challenger_data[challenger_id]["word"] = word

    await callback_query.message.edit_text(
        f"🔥 **The challenge has started!**\n"
        f"🔤 **Word length:** `{word_length}`\n"
        f"💰 **Bet Pool:** `{bet_amount * 2} points`\n"
        f"🤔 *Both players, start guessing!*"
    )

@app.on_callback_query(filters.regex("^decline_"))
async def decline_challenge(client, callback_query):
    opponent_id = callback_query.from_user.id
    challenger_id = int(callback_query.data.split("_")[1])

    if challenger_id not in challenger_data or challenger_data[challenger_id]["opponent_id"] != opponent_id:
        await callback_query.answer("⚠️ You cannot decline this challenge!", show_alert=True)
        return

    del challenger_data[challenger_id]
    await callback_query.message.edit_text("🚫 **Challenge declined.**")


