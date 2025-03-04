import random
import requests
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from database import get_user_points, update_user_points  # Import functions for point management

# Store ongoing challenges
challenger_data = {}

# Fallback words in case API fails
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

# Preload word lists
word_lists = {length: fetch_words(length) for length in fallback_words}

def get_random_word(word_length):
    return random.choice(word_lists[word_length])

@app.on_message(filters.command("challenge"))
async def handle_challenge(client, message):
    args = message.text.split()
    if len(args) != 3 or not args[2].isdigit():
        await message.reply("⚠️ Usage: `/challenge @username bet_amount`", quote=True)
        return

    if not message.reply_to_message:
        await message.reply("⚠️ Please reply to the user you want to challenge!", quote=True)
        return

    challenger_id = message.from_user.id
    opponent = message.reply_to_message.from_user
    bet_amount = int(args[2])

    if bet_amount <= 0:
        await message.reply("⚠️ Bet amount must be greater than 0.", quote=True)
        return

    challenger_points = get_user_points(challenger_id)
    opponent_points = get_user_points(opponent.id)

    if challenger_points < bet_amount:
        await message.reply("❌ You don't have enough points! Earn points by playing new games.", quote=True)
        return

    if opponent_points < bet_amount:
        await message.reply(f"❌ {opponent.mention} doesn't have enough points!", quote=True)
        return

    challenger_data[challenger_id] = {
        "opponent_id": opponent.id,
        "bet_amount": bet_amount
    }

    buttons = [
        [InlineKeyboardButton("4 Letters", callback_data=f"challenge_length_4_{challenger_id}")],
        [InlineKeyboardButton("5 Letters", callback_data=f"challenge_length_5_{challenger_id}")],
        [InlineKeyboardButton("6 Letters", callback_data=f"challenge_length_6_{challenger_id}")],
        [InlineKeyboardButton("7 Letters", callback_data=f"challenge_length_7_{challenger_id}")],
    ]

    await message.reply(
        f"🎯 {opponent.mention}, {message.from_user.mention} has challenged you to a game!\n"
        f"💰 Bet Amount: **{bet_amount} points**\n\n"
        "🔢 Challenger, select a word length:",
        reply_markup=InlineKeyboardMarkup(buttons),
        quote=True
    )

@app.on_callback_query(filters.regex("^challenge_length_"))
async def select_challenge_length(client, callback_query):
    data = callback_query.data.split("_")
    word_length = int(data[2])
    challenger_id = int(data[3])
    user_id = callback_query.from_user.id

    if challenger_id != user_id:
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
        f"✅ {callback_query.from_user.mention} has chosen a **{word_length}-letter** word!\n"
        f"👤 {callback_query.message.chat.get_member(opponent_id).user.mention}, do you accept the challenge?",
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

    # Deduct bet amount from both players
    update_user_points(challenger_id, -bet_amount)
    update_user_points(opponent_id, -bet_amount)

    challenger_data[challenger_id]["word"] = word

    await callback_query.message.edit_text(
        f"🔥 The challenge has started!\n"
        f"🔤 The word has **{word_length}** letters.\n"
        f"💰 Total Bet Pool: **{bet_amount * 2} points**\n"
        f"🤔 Both players, start guessing!"
    )

@app.on_callback_query(filters.regex("^decline_"))
async def decline_challenge(client, callback_query):
    await callback_query.message.edit_text("🚫 Challenge declined.")

@app.on_message(filters.text)
async def process_challenge_guess(client, message):
    user_id = message.from_user.id
    text = message.text.strip().lower()

    for challenger_id, game_data in challenger_data.items():
        if user_id in [challenger_id, game_data.get("opponent_id")]:
            word = game_data["word"]
            bet_amount = game_data["bet_amount"]

            if len(text) != len(word):
                await message.reply("⚠️ Invalid guess length!")
                return

            feedback = ""
            word_list = list(word)

            for i, letter in enumerate(text):
                if letter == word[i]:
                    feedback += "🟩"
                    word_list[i] = None
                elif letter in word_list:
                    feedback += "🟨"
                    word_list[word_list.index(letter)] = None
                else:
                    feedback += "🟥"

            await message.reply(f"{feedback} → {text.upper()}")

            if text == word:
                winner_id = user_id
                loser_id = game_data["opponent_id"] if user_id == challenger_id else challenger_id
                total_winnings = bet_amount * 2

                # Deduct bet amount from the loser and award winnings to the winner
                update_user_points(loser_id, -bet_amount)
                update_user_points(winner_id, total_winnings)

                del challenger_data[challenger_id]

                await message.reply(
                    f"🎉 Congratulations {message.from_user.mention}! 🎉\n"
                    f"You guessed the word **{word.upper()}** correctly!\n"
                    f"💰 You won **{total_winnings} points**!"
                )
            return
