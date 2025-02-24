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
normal_games = {}
challenge_games = {}
challenges = {}
challenge_word_length = {}
# Pending challenge requests; key: frozenset({challenger, opponent})

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
async def process_guess(client: Client, message: Message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    guess = message.text.strip().lower()

    # Check if this is a normal game
    if chat_id in normal_games:
        game = normal_games[chat_id]
        word = game["word"]
        if len(guess) != len(word) or guess in game["used_words"]:
            return
        game["used_words"].add(guess)
        feedback = check_guess(guess, word)
        game["history"].append(f"{feedback} → {guess.upper()}")
        await message.reply("\n".join(game["history"]))
        if guess == word:
            update_chat_score(chat_id, user_id)
            update_global_score(user_id)
            await message.reply(f"🎉 Congratulations {message.from_user.first_name}! You guessed the word **{word.upper()}** correctly!")
            del normal_games[chat_id]
        return

    # Check if the user is in a challenge game
    for key, game in list(challenge_games.items()):
        if user_id in key and chat_id == game["chat_id"]:
            word = game["word"]
            if len(guess) != len(word) or guess in game["used_words"]:
                return
            game["used_words"].add(guess)
            feedback = check_guess(guess, word)
            game["history"].append(f"{feedback} → {guess.upper()}")
            await message.reply("\n".join(game["history"]))
            if guess == word:
                # Determine the winner and loser
                winner = user_id
                loser = next(uid for uid in key if uid != winner)
                bet_amount = game["bet_amount"]

                
                update_chat_score(chat_id, winner, +bet_amount * 2)  # 
                update_chat_score(chat_id, loser, -bet_amount)
                
              
                winner_user = await client.get_users(winner)
                loser_user = await client.get_users(loser)
                await message.reply(f"🎉 {winner_user.first_name} wins! The word was **{word.upper()}**. {bet_amount} points have been transferred from {loser_user.first_name} to {winner_user.first_name}.")

                del challenge_games[key]
              
          
            return

    # If no game is active, ignore guesses
    return


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


@app.on_message(filters.command("challenge"))
async def challenge_user(client: Client, message: Message):
    if len(message.command) < 3:
        await message.reply("Usage: /challenge @username <bet_amount>")
        return

    challenger = message.from_user.id
    opponent_username = message.command[1]
    try:
        opponent_user = await client.get_users(opponent_username)
        opponent = opponent_user.id
    except Exception:
        await message.reply("Invalid username.")
        return

    if challenger == opponent:
        await message.reply("You can't challenge yourself!")
        return

    # Get the bet amount
    try:
        bet_amount = int(message.command[2])
        if bet_amount <= 0:
            raise ValueError
    except ValueError:
        await message.reply("Please enter a valid positive bet amount.")
        return

    # Check if both players have enough balance
    challenger_balance = get_user_balance(challenger)
    opponent_balance = get_user_balance(opponent)
    
    if challenger_balance < bet_amount:
        await message.reply("You don't have enough points to place this bet!")
        return
    
    if opponent_balance < bet_amount:
        await message.reply(f"{opponent_user.first_name} does not have enough points to accept this bet!")
        return

    # Store the challenge details
    challenge_key = frozenset({challenger, opponent})
    challenges[challenge_key] = {
        "challenger": challenger,
        "opponent": opponent,
        "bet_amount": bet_amount
    }

    buttons = [[InlineKeyboardButton(f"{i} Letters", callback_data=f"set_length_{challenger}_{opponent}_{bet_amount}_{i}")] for i in range(4, 8)]
    await message.reply("Choose a word length for the challenge:", reply_markup=InlineKeyboardMarkup(buttons))



@app.on_callback_query(filters.regex(r"^set_length_(\d+)_(\d+)_(\d+)_(\d+)$"))
async def set_challenge_length(client, callback_query):
    challenger, opponent, bet_amount, word_length = map(int, callback_query.data.split("_")[2:])
    challenge_key = frozenset({challenger, opponent})

    if challenge_key in challenges:
        challenges[challenge_key]["word_length"] = word_length

        buttons = [[InlineKeyboardButton("✅ Accept", callback_data=f"challenge_accept_{challenger}_{opponent}_{bet_amount}_{word_length}")]]
        await callback_query.message.edit_text(
            f"{opponent}, {challenger} has challenged you for a {word_length}-letter word game with a bet of {bet_amount} points!\n\nDo you accept?",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

        
@app.on_callback_query(filters.regex(r"^challenge_accept_(\d+)_(\d+)_(\d+)_(\d+)$"))
async def accept_challenge(client, callback_query):
    challenger, opponent, bet_amount, word_length = map(int, callback_query.data.split("_")[2:])
    challenge_key = frozenset({challenger, opponent})

    if callback_query.from_user.id != opponent:
        await callback_query.answer("This challenge is not for you.", show_alert=True)
        return

    if challenge_key not in challenges:
        await callback_query.answer("Challenge not found.", show_alert=True)
        return

    chat_id = callback_query.message.chat.id
    word = start_new_game(word_length)

    # Deduct bet amount from both players
    update_chat_score(chat_id, challenger, -bet_amount)
    update_chat_score(chat_id, opponent, -bet_amount)
    

    challenge_games[challenge_key] = {
        "word": word,
        "history": [],
        "used_words": set(),
        "chat_id": chat_id,
        "bet_amount": bet_amount,
        "players": {challenger, opponent}
    }
    del challenges[challenge_key]

    await callback_query.message.edit_text(
        f"🔥 Challenge accepted! A {word_length}-letter word has been chosen. Start guessing!"
    )


@app.on_message(filters.text)
async def process_guess(client: Client, message: Message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    guess = message.text.strip().lower()

    for key, game in list(challenge_games.items()):
        if chat_id == game["chat_id"]:
            if user_id not in game["players"]:
                players = list(game["players"])
                challenger_user = await client.get_users(players[0])
                opponent_user = await client.get_users(players[1])
                await message.reply(
                    f"This challenge is between {challenger_user.first_name} and {opponent_user.first_name}, please don't interfere."
                )
                return
            
            word = game["word"]
            if len(guess) != len(word) or guess in game["used_words"]:
                return
            game["used_words"].add(guess)
            feedback = check_guess(guess, word)
            game["history"].append(f"{feedback} → {guess.upper()}")
            await message.reply("\n".join(game["history"]))

            if guess == word:
                # Determine the winner and loser
                winner = user_id
                loser = next(uid for uid in key if uid != winner)
                bet_amount = game["bet_amount"]

              
                
                # Transfer bet amount from loser to winner
              
                winner_user = await client.get_users(winner)
                loser_user = await client.get_users(loser)
                await message.reply(f"🎉 {winner_user.first_name} wins! The word was **{word.upper()}**. {bet_amount} points have been transferred from {loser_user.first_name} to {winner_user.first_name}.")

                del challenge_games[key]
            return

          

app.run()
