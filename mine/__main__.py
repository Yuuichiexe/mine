import random
import os
import requests
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from database import (update_global_score, update_chat_score,
                      get_global_leaderboard, get_chat_leaderboard,
                      initialize_db, get_user_balance)

# Initialize the database (creates DB/tables if they don't exist)
initialize_db()

# Fallback words in case the API fails
fallback_words = {
    4: ["play", "word", "game", "chat"],
    5: ["guess", "brain", "smart", "think"],
    6: ["random", "puzzle", "letter", "breeze"],
    7: ["amazing", "thought", "journey", "fantasy"]
}

# Function to fetch words from Datamuse API
def fetch_words(word_length, max_words=100000):
    try:
        response = requests.get(f"https://api.datamuse.com/words?sp={'?' * word_length}&max=1000")
        response.raise_for_status()
        words = [word["word"] for word in response.json()]
        return words if words else fallback_words[word_length]
    except requests.RequestException:
        return fallback_words[word_length]

# Load word lists for each length
word_lists = {length: fetch_words(length) for length in fallback_words}

# Dictionaries to store games and challenges
normal_games = {}       # Key: chat_id, value: game dict for normal (chat) games
challenge_games = {}    # Key: frozenset({challenger, opponent}), value: game dict for challenge games
challenges = {}         # Pending challenge requests; key: frozenset({challenger, opponent})

# Bot credentials
API_ID = int(os.getenv("API_ID", "20222660"))
API_HASH = os.getenv("API_HASH", "5788f1f4a93f2de28835a0cf1b0ebae4")
BOT_TOKEN = os.getenv("BOT_TOKEN", "6694970760:AAFv6Zm9Av8HrY7JOTohg0E6c53Ar036eDc")

app = Client("word_guess_bot", bot_token=BOT_TOKEN, api_id=API_ID, api_hash=API_HASH)

# Helper functions
def start_new_game(word_length):
    """Return a random word of the given length."""
    return random.choice(word_lists[word_length])

def is_valid_english_word(word):
    """Check if a word is valid using the Datamuse API."""
    try:
        response = requests.get(f"https://api.datamuse.com/words?sp={word}&max=1")
        response.raise_for_status()
        return word in [w["word"] for w in response.json()]
    except requests.RequestException:
        return False

def check_guess(guess, word):
    """Return feedback string using green, yellow, and red squares."""
    feedback = [None] * len(word)
    word_list = list(word)
    # First pass: correct letters (green)
    for i in range(len(word)):
        if guess[i] == word[i]:
            feedback[i] = "🟩"
            word_list[i] = None
    # Second pass: letter exists (yellow) or not (red)
    for i in range(len(word)):
        if feedback[i] is None:
            if guess[i] in word_list:
                feedback[i] = "🟨"
                word_list[word_list.index(guess[i])] = None
            else:
                feedback[i] = "🟥"
    return ''.join(feedback)

# ---------------- Normal (Chat) Games ----------------

@app.on_message(filters.command("start"))
async def start_command(client: Client, message: Message):
    user_name = message.from_user.first_name
    welcome_text = (
        f"Hello {user_name}! Welcome to **Word Mine Bot**! 🎮\n\n"
        "How to Play:\n"
        "- Start a new game with /new\n"
        "- Choose word length\n"
        "- Guess the word and win points!\n"
        "- Check leaderboard with /leaderboard\n"
    )
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Add to Group", url=f"https://t.me/{client.me.username}?startgroup=true")],
        [InlineKeyboardButton("⚙️ Commands", callback_data="commands")]
    ])
    await message.reply_text(welcome_text, reply_markup=buttons)

@app.on_callback_query(filters.regex("^commands$"))
async def show_commands(client, callback_query):
    commands_text = (
        "**Commands:**\n"
        "- /start - Start the bot\n"
        "- /new - Start a new normal game\n"
        "- /challenge - Challenge a user\n"
        "- /leaderboard - Global leaderboard\n"
        "- /chatleaderboard - Chat leaderboard\n"
        "- /end - End current normal game\n"
        "- /help - Show help message\n"
    )
    await callback_query.message.edit_text(commands_text)

@app.on_message(filters.command("new"))
async def new_game(client: Client, message: Message):
    buttons = [[InlineKeyboardButton(f"{i} Letters", callback_data=f"normal_{i}")] for i in range(4, 8)]
    await message.reply("Choose a word length for a new game:", reply_markup=InlineKeyboardMarkup(buttons))

@app.on_callback_query(filters.regex("^normal_"))
async def start_normal_game(client, callback_query):
    word_length = int(callback_query.data.split("_")[1])
    word = start_new_game(word_length)
    chat_id = callback_query.message.chat.id
    normal_games[chat_id] = {"word": word, "history": [], "used_words": set()}
    await callback_query.message.edit_text(f"A new {word_length}-letter game has started! Start guessing!")

@app.on_message(filters.text & ~filters.command(["new", "leaderboard", "chatleaderboard", "end", "help", "challenge"]))
async def guess_normal_game(client: Client, message: Message):
    chat_id = message.chat.id
    if chat_id not in normal_games:
        return
    game = normal_games[chat_id]
    guess = message.text.strip().lower()
    word = game["word"]
    if len(guess) != len(word):
        return
    if guess in game["used_words"]:
        await message.reply("You already guessed that word!")
        return
    game["used_words"].add(guess)
    feedback = check_guess(guess, word)
    game["history"].append(f"{feedback} → {guess.upper()}")
    await message.reply("\n".join(game["history"]))
    if guess == word:
        update_chat_score(chat_id, message.from_user.id)
        update_global_score(message.from_user.id)
        del normal_games[chat_id]
        await message.reply(f"🎉 Congratulations {message.from_user.first_name}! You guessed the word **{word.upper()}** correctly!")

# ---------------- Challenge (Head-to-Head) Games ----------------

@app.on_message(filters.command("challenge"))
async def challenge_user(client: Client, message: Message):
    if len(message.command) < 3:
        await message.reply("Usage: /challenge @username points")
        return

    challenger = message.from_user.id
    opponent_username = message.command[1]
    try:
        opponent_user = await client.get_users(opponent_username)
        opponent = opponent_user.id
    except Exception:
        await message.reply("Invalid username. Make sure the opponent exists.")
        return

    if challenger == opponent:
        await message.reply("You can't challenge yourself!")
        return

    bet_points = int(message.command[2])
    # Query DB for opponent's balance
    opponent_balance = get_user_balance(opponent)
    if opponent_balance < bet_points:
        await message.reply(
            f"🚨 {opponent_username}, you don't have enough points! You have {opponent_balance} points.\n"
            "Reply with a new bet amount."
        )
        challenges[frozenset({challenger, opponent})] = {"bet_pending": True, "challenger": challenger}
        return

    challenges[frozenset({challenger, opponent})] = {"bet": bet_points}
    buttons = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Accept", callback_data=f"challenge_accept_{challenger}_{opponent}_{bet_points}")
    ]])
    await message.reply(
        f"💥 {message.from_user.first_name} has challenged {opponent_username} for {bet_points} points!\n"
        f"{opponent_username}, click 'Accept' to start the challenge.",
        reply_markup=buttons
    )

@app.on_message(filters.text & filters.reply)
async def handle_bet_response(client: Client, message: Message):
    opponent = message.from_user.id
    challenge_key = next((k for k, v in challenges.items() if opponent in k and v.get("bet_pending")), None)
    if not challenge_key:
        return
    challenger = challenges[challenge_key]["challenger"]
    try:
        new_bet = int(message.text.strip())
    except ValueError:
        await message.reply("Please enter a valid number.")
        return
    opponent_balance = get_user_balance(opponent)
    if new_bet <= 0 or new_bet > opponent_balance:
        await message.reply("Invalid bet amount. Please try again.")
        return
    challenges[challenge_key] = {"bet": new_bet}
    buttons = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Accept", callback_data=f"challenge_accept_{challenger}_{opponent}_{new_bet}")
    ]])
    await message.reply(f"Challenge updated! New bet: {new_bet} points.", reply_markup=buttons)

@app.on_callback_query(filters.regex(r"^challenge_accept_(\d+)_(\d+)_(\d+)$"))
async def accept_challenge(client, callback_query):
    # Acknowledge the callback query
    await callback_query.answer("Challenge accepted!")
    data = callback_query.data.split("_")
    # Data format: challenge_accept_{challenger}_{opponent}_{bet_points}
    challenger = int(data[2])
    opponent = int(data[3])
    bet_points = int(data[4])
    key = frozenset({challenger, opponent})
    if key not in challenges:
        await callback_query.answer("Challenge not found.", show_alert=True)
        return
    # Store the chat id along with the challenge game so that only messages from that chat are processed.
    chat_id = callback_query.message.chat.id
    word_length = random.choice([4, 5, 6, 7])
    word = random.choice(word_lists[word_length])
    challenge_games[key] = {"word": word, "history": [], "used_words": set(), "bet": bet_points, "chat_id": chat_id}
    await callback_query.message.edit_text(
        f"🔥 Challenge accepted! A {word_length}-letter word has been chosen.\n"
        f"First to guess wins {bet_points} points!"
    )
    del challenges[key]

@app.on_message(filters.text & ~filters.command(["challenge"]))
async def guess_challenge_game(client: Client, message: Message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    # Process guesses only for challenge games in the same chat and for the involved users.
    for key, game in list(challenge_games.items()):
        if user_id in key and chat_id == game.get("chat_id"):
            guess = message.text.strip().lower()
            word = game["word"]
            if len(guess) != len(word):
                return
            if guess in game["used_words"]:
                await message.reply("You already guessed that!")
                return
            game["used_words"].add(guess)
            game["history"].append(f"{check_guess(guess, word)} → {guess.upper()}")
            await message.reply("\n".join(game["history"]))
            if guess == word:
                update_chat_score(chat_id, user_id, game["bet"])
                update_global_score(user_id, game["bet"])
                await message.reply(f"🎉 {message.from_user.first_name} wins the challenge! The word was {word.upper()}.")
                del challenge_games[key]
            return

# ---------------- Leaderboards & End Command ----------------

@app.on_message(filters.command("leaderboard"))
async def leaderboard(client: Client, message: Message):
    leaderboard_list = get_global_leaderboard()
    if not leaderboard_list:
        await message.reply("No leaderboard entries yet.")
        return
    text = "🌍 **Global Leaderboard:**\n\n"
    for rank, (uid, score) in enumerate(leaderboard_list, start=1):
        try:
            user = await client.get_users(uid)
            name = user.first_name
        except Exception:
            name = f"User {uid}"
        text += f"🏅 **#{rank}** - {name} → **{score} POINTS**\n"
    await message.reply(text)

@app.on_message(filters.command("chatleaderboard"))
async def chat_leaderboard(client: Client, message: Message):
    leaderboard_list = get_chat_leaderboard(message.chat.id)
    if not leaderboard_list:
        await message.reply("No leaderboard entries yet.")
        return
    text = "🏆 **Chat Leaderboard:**\n\n"
    for rank, (uid, score) in enumerate(leaderboard_list, start=1):
        try:
            user = await client.get_users(uid)
            name = user.first_name
        except Exception:
            name = f"User {uid}"
        text += f"🏅 **#{rank}** - {name} → **{score} POINTS**\n"
    await message.reply(text)

@app.on_message(filters.command("end"))
async def end_game(client: Client, message: Message):
    chat_id = message.chat.id
    if chat_id in normal_games:
        del normal_games[chat_id]
        await message.reply("🚫 The normal game has been ended. Start a new one with /new!")
    else:
        await message.reply("⚠️ No active normal game to end.")

@app.on_message(filters.command("help"))
async def help_command(client: Client, message: Message):
    help_text = (
        "**Word Mine Bot Help**\n\n"
        "- /start - Start the bot and see the welcome message\n"
        "- /new - Start a new normal game\n"
        "- /challenge - Challenge a user for a head-to-head game\n"
        "- /leaderboard - Global leaderboard\n"
        "- /chatleaderboard - Chat leaderboard\n"
        "- /end - End the current normal game\n"
        "- /help - Show this help message\n"
    )
    await message.reply(help_text)

app.run()
