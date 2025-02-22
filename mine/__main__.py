import random
import os
import requests
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
from database import update_global_score, update_chat_score, get_global_leaderboard, get_chat_leaderboard

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
        response = requests.get(f"https://api.datamuse.com/words?sp={'?' * word_length}&max={max_words}")
        response.raise_for_status()
        words = [word["word"] for word in response.json()]
        return words if words else fallback_words[word_length]
    except requests.RequestException:
        return fallback_words[word_length]

# Fetch words for different lengths
word_lists = {length: fetch_words(length) for length in fallback_words}

# Game data storage
group_games = {}
challenges = {}
user_points = {}  # Dictionary to store user points

# Bot credentials
API_ID = int(os.getenv("API_ID", "20222660"))
API_HASH = os.getenv("API_HASH", "5788f1f4a93f2de28835a0cf1b0ebae4")
BOT_TOKEN = os.getenv("BOT_TOKEN", "7560532835:AAE5yA7zLwHrkJQK0VYeGeCR-Db6Jhqzvpo")

app = Client("word_guess_bot", bot_token=BOT_TOKEN, api_id=API_ID, api_hash=API_HASH)

# Start a new game
def start_new_game(word_length):
    return random.choice(word_lists[word_length])

# Check if a word is valid
def is_valid_english_word(word):
    try:
        response = requests.get(f"https://api.datamuse.com/words?sp={word}&max=1")
        response.raise_for_status()
        return word in [w["word"] for w in response.json()]
    except requests.RequestException:
        return False

# Check a user's guess
def check_guess(guess, word_to_guess):
    feedback = []
    word_to_guess_list = list(word_to_guess)
    
    for i in range(len(word_to_guess)):
        if guess[i] == word_to_guess[i]:
            feedback.append("🟩")
            word_to_guess_list[i] = None  
        else:
            feedback.append(None)
    
    for i in range(len(word_to_guess)):
        if feedback[i] is None and guess[i] in word_to_guess_list:
            feedback[i] = "🟨"
            word_to_guess_list[word_to_guess_list.index(guess[i])] = None  
        elif feedback[i] is None:
            feedback[i] = "🟥"
    
    return ''.join(feedback)


@app.on_message(filters.command("start"))
async def start_command(client: Client, message: Message):
    user_id = message.from_user.id
    user_name = message.from_user.first_name
    mention = f"[{user_name}](tg://user?id={user_id})"

    
    welcome_text = (
        f"<b>Yo, Word miners! {mention} in the house! 🧙‍♂️ Welcome to the ultimate Word Mine Bot showdown!</b>\n\n"
        "<b>🕹️ How to Play:</b>\n"
        "<u><i>- Start a new game using</u> /new</i>\n"
        "<u><i>- Choose a word length</i></u>\n"
        "<u><i>- Guess the word and get results with 🟩🟨🟥</i></u>\n"
        "<u><i>- Score points and climb the leaderboard!</i></u>\n\n"
        "<i>Ready to crush your friends? Bring the battle to your group! ⚔️ Add me and let the word wars begin!</i>"
    )
    
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Add to Group", url=f"https://t.me/{client.me.username}?startgroup=true")],
        [InlineKeyboardButton("⚙️ Bot Commands", callback_data="commands"),
         InlineKeyboardButton("🛡Support chat", url=f"https://t.me/WordMiners")
        ]
    ])
    
    await message.reply_photo(
        photo="https://files.catbox.moe/3qhaq0.jpg",  # Replace with an actual image URL
        caption=welcome_text,
        reply_markup=buttons
    )

@app.on_callback_query(filters.regex("^commands$"))
async def show_commands(client, callback_query):
    commands_text = (
        "**Word Mine Bot Help**\n\n"
        "🎮 **Commands:**\n"
        "- /start - Start the bot and see the welcome message\n"
        "- /new - Start a new word guessing game\n"
        "- /end - End the current game\n"
        "- /leaderboard - View the global leaderboard\n"
        "- /chatleaderboard - View the chat leaderboard\n"
        "- /help - Show this help message\n"
    )
    
    await callback_query.message.edit_text(commands_text, reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Back", callback_data="back_to_start")]
    ]))


@app.on_callback_query(filters.regex("^back_to_start$"))
async def back_to_start(client, callback_query):
    await callback_query.message.delete()  # Delete the previous message
    await start_command(client, callback_query.message)  # Send a new start message

@app.on_message(filters.command("challenge"))
async def challenge_user(client: Client, message: Message):
    if len(message.command) < 3:
        await message.reply("Usage: /challenge @username points")
        return
    
    challenger = message.from_user.id
    opponent_username = message.command[1]
    bet_points = int(message.command[2])

    if opponent_username.startswith("@"):  # Convert username to user_id
        try:
            opponent_user = await client.get_users(opponent_username)
            opponent = opponent_user.id
        except Exception:
            await message.reply("Invalid username. Make sure the opponent exists.")
            return
    else:
        await message.reply("You must tag a valid user with @username.")
        return

    if challenger == opponent:
        await message.reply("You can't challenge yourself!")
        return

    # Check if opponent has enough points
    opponent_points = user_points.get(opponent, 0)
    if opponent_points < bet_points:
        await message.reply(
            f"🚨 {opponent_username}, you don't have enough points! You have {opponent_points} points."
            "\nHow many points would you like to bet? Reply with a number."
        )
        challenges[frozenset({challenger, opponent})] = {"bet_pending": True, "challenger": challenger}
        return

    # Store challenge
    challenges[frozenset({challenger, opponent})] = {"bet": bet_points}

    # Send challenge with Accept button
    await message.reply(
        f"💥 {message.from_user.first_name} has challenged {opponent_username} for {bet_points} points!",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Accept", callback_data=f"accept_{challenger}_{opponent}_{bet_points}")]
        ])
    )

@app.on_message(filters.text & filters.reply)
async def handle_bet_response(client: Client, message: Message):
    opponent = message.from_user.id
    challenge_key = next((k for k in challenges.keys() if opponent in k and "bet_pending" in challenges[k]), None)

    if not challenge_key:
        return

    challenger = challenges[challenge_key]["challenger"]
    try:
        new_bet = int(message.text.strip())
        if new_bet <= 0 or new_bet > user_points.get(opponent, 0):
            await message.reply("Invalid amount. Please enter a valid number within your available points.")
            return
    except ValueError:
        await message.reply("Please enter a valid number.")
        return

    # Update the challenge with the new bet amount
    challenges[challenge_key] = {"bet": new_bet}

    # Send challenge with Accept button
    await message.reply(
        f"💥 Challenge updated! {message.from_user.first_name} is betting {new_bet} points!",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Accept", callback_data=f"accept_{challenger}_{opponent}_{new_bet}")]
        ])
    )

@app.on_callback_query(filters.regex(r"^accept_(\d+)_(\d+)_(\d+)$"))
async def accept_challenge(client: Client, callback_query):
    data = callback_query.data.split("_")
    challenger = int(data[1])
    opponent = int(data[2])
    bet_points = int(data[3])
    challenge_key = frozenset({challenger, opponent})

    if challenge_key not in challenges:
        await callback_query.answer("Challenge not found.", show_alert=True)
        return

    word_length = random.choice([4, 5, 6, 7])
    word_to_guess = random.choice(word_lists[word_length])

    group_games[challenge_key] = {
        "word": word_to_guess,
        "history": [],
        "used_words": set(),
        "bet": bet_points
    }

    await callback_query.message.edit_text(
        f"🔥 Challenge accepted! A {word_length}-letter word has been chosen!"
        f"\n**{challenger} vs {opponent}** - First to guess wins {bet_points} points!"
    )
    
    del challenges[challenge_key]

@app.on_message(filters.text & ~filters.command(["challenge"]))
async def guess_word(client: Client, message: Message):
    user_id = message.from_user.id

    for game_key, game in group_games.items():
        if user_id in game_key:
            guess = message.text.strip().lower()
            word_to_guess = game["word"]

            if len(guess) != len(word_to_guess):
                return  

            if guess == word_to_guess:
                winner = user_id
                loser = next(user for user in game_key if user != winner)

                update_chat_score(message.chat.id, winner, game["bet"])
                update_global_score(winner, game["bet"])

                await message.reply(
                    f"🎉 {message.from_user.first_name} guessed **{word_to_guess.upper()}** and won **{game['bet']} points!**"
                )
                del group_games[game_key]
                return

            await message.reply("❌ Incorrect guess! Try again.")

@app.on_message(filters.command("new"))
async def new_game(client: Client, message: Message):
    chat_id = message.chat.id
    buttons = [[InlineKeyboardButton(f"{i} Letters", callback_data=f"start_{i}")] for i in range(4, 8)]
    await message.reply("Choose a word length to start the game:", reply_markup=InlineKeyboardMarkup(buttons))

@app.on_callback_query()
async def select_word_length(client, callback_query):
    await callback_query.answer()
    chat_id = callback_query.message.chat.id
    word_length = int(callback_query.data.split("_")[1])
    
    word_to_guess = start_new_game(word_length)
    group_games[chat_id] = {"word": word_to_guess, "history": [], "used_words": set()}
    
    await callback_query.message.edit_text(f"A new {word_length}-letter game has started! Guess a word.")

@app.on_message(filters.text & ~filters.command(["new", "leaderboard", "chatleaderboard", "end", "help"]))
async def guess_word(client: Client, message: Message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    user_name = message.from_user.first_name
    mention = f"[{user_name}](tg://user?id={user_id})"

    if chat_id not in group_games:
        return

    word_to_guess = group_games[chat_id]["word"]
    guess = message.text.strip().lower()

    if len(guess) != len(word_to_guess):
        return  

    if not is_valid_english_word(guess):
        await message.reply(f"❌ {mention}, this word is not valid. Try another one!")
        return

    if guess in group_games[chat_id]["used_words"]:
        await message.reply(f"🔄 {mention}, you already used this word! Try a different one.")
        return

    group_games[chat_id]["used_words"].add(guess)
    feedback = check_guess(guess, word_to_guess)
    
    group_games[chat_id]["history"].append(f"{feedback} → {guess.upper()}")
    guess_history = "\n".join(group_games[chat_id]["history"])
    
    await message.reply(guess_history)

    if guess == word_to_guess:
        update_chat_score(chat_id, user_id)
        update_global_score(user_id)
        
        leaderboard = get_global_leaderboard()
        user_score = next((score for uid, score in leaderboard if uid == user_id), 0)
        user_rank = next((i + 1 for i, (uid, _) in enumerate(leaderboard) if uid == user_id), "Unranked")

        del group_games[chat_id]
        
        await message.reply(
            f"🎉 Congratulations {mention}! 🎉\n"
            f"You guessed the word **{word_to_guess.upper()}** correctly!\n"
            f"🏆 You earned **1 point**!\n"
            f"📊 Your total score: **{user_score}**\n"
            f"🌍 Your global rank: **#{user_rank}**"
        )

@app.on_message(filters.command("leaderboard"))
async def leaderboard(client: Client, message: Message):
    leaderboard = get_global_leaderboard()
    if not leaderboard:
        await message.reply("No scores recorded yet.")
        return
    
    leaderboard_text = "🌍 **Global Leaderboard:**\n\n"
    
    for rank, (user_id, score) in enumerate(leaderboard, start=1):
        try:
            user = await client.get_users(user_id)  # Fetch user info
            mention = f"[{user.first_name}](tg://user?id={user.id})"
        except Exception:  # Handle unknown users
            mention = f"User {user_id}"

        leaderboard_text += f"🏅 **#{rank}** - {mention} → **{score} POINTS**\n"
    
    await message.reply(leaderboard_text)


@app.on_message(filters.command("chatleaderboard"))
async def chat_leaderboard(client: Client, message: Message):
    leaderboard = get_chat_leaderboard(message.chat.id)
    if not leaderboard:
        await message.reply("No scores recorded in this chat yet.")
        return

    leaderboard_text = "🏆 **Chat Leaderboard:**\n\n"

    for rank, (user_id, score) in enumerate(leaderboard, start=1):
        try:
            user = await client.get_users(user_id)  # Fetch user info
            mention = f"[{user.first_name}](tg://user?id={user.id})"
        except Exception:  # Handle unknown users
            mention = f"User {user_id}"

        leaderboard_text += f"🏅 **#{rank}** - {mention} → **{score} POINTS**\n"
    
    await message.reply(leaderboard_text)


@app.on_message(filters.command("end"))
async def end_game(client: Client, message: Message):
    chat_id = message.chat.id
    
    if chat_id in group_games:
        del group_games[chat_id]
        await message.reply("🚫 The game has been ended. Start a new one with /new!")
    else:
        await message.reply("⚠️ No active game to end.")

@app.on_message(filters.command("help"))
async def help_command(client: Client, message: Message):
    help_text = (
        "**Word Mine Bot Help**\n\n"
        "🎮 **Commands:**\n"
        "- /start - Start the bot and see the welcome message\n"
        "- /new - Start a new word guessing game\n"
        "- /end - End the current game\n"
        "- /leaderboard - View the global leaderboard\n"
        "- /chatleaderboard - View the chat leaderboard\n"
        "- /help - Show this help message\n"
        
    )
    await message.reply(help_text)
    

app.run()
