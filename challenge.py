import random
import requests
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from database import get_user_score, deduct_points, add_points

# Challenge tracking
challenges = {}
challenge_games = {}

# Fetch words from API
def fetch_words(word_length):
    try:
        response = requests.get(f"https://api.datamuse.com/words?sp={'?' * word_length}&max=1000", timeout=5)
        response.raise_for_status()
        words = [word["word"] for word in response.json()]
        return words if words else ["guess", "smart", "brain"]
    except requests.RequestException:
        return ["guess", "smart", "brain"]

word_lists = {length: fetch_words(length) for length in range(4, 8)}

def start_new_game(word_length):
    return random.choice(word_lists[word_length])

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

async def challenge_player(client, message):
    args = message.command[1:]
    if len(args) < 3:
        await message.reply("Usage: `/challenge @username points word_length`")
        return

    opponent_mention = args[0]
    bet_points = int(args[1])
    word_length = int(args[2])
    
    if not (4 <= word_length <= 7):
        await message.reply("Word length must be between 4 and 7 letters!")
        return
    
    if message.reply_to_message:
        opponent_id = message.reply_to_message.from_user.id
    else:
        opponent_id = await client.get_users(opponent_mention.strip("@"))
        opponent_id = opponent_id.id if opponent_id else None

    if not opponent_id:
        await message.reply("Invalid opponent! Mention a valid user or reply to their message.")
        return

    challenger_id = message.from_user.id
    challenger_score = get_user_score(challenger_id)
    opponent_score = get_user_score(opponent_id)

    if challenger_score < bet_points or opponent_score < bet_points:
        await message.reply("One or both players don't have enough points for this challenge.")
        return

    challenges[opponent_id] = {
        "challenger": challenger_id,
        "bet": bet_points,
        "word_length": word_length
    }

    challenge_text = (f"🔥 {message.from_user.first_name} challenged you to a Word Mine duel! 🔥\n"
                      f"💰 **Bet:** {bet_points} points\n"
                      f"🔡 **Word Length:** {word_length} letters\n\n"
                      f"Do you accept the challenge?")

    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Accept", callback_data=f"accept_{opponent_id}")],
        [InlineKeyboardButton("❌ Decline", callback_data=f"decline_{opponent_id}")]
    ])

    await message.reply(challenge_text, reply_markup=buttons)

async def accept_challenge(client, callback_query):
    opponent_id = int(callback_query.data.split("_")[1])
    challenge = challenges.pop(opponent_id, None)

    if not challenge or callback_query.from_user.id != opponent_id:
        await callback_query.answer("This challenge is no longer valid.", show_alert=True)
        return

    challenger_id = challenge["challenger"]
    bet_points = challenge["bet"]
    word_length = challenge["word_length"]

    deduct_points(challenger_id, bet_points)
    deduct_points(opponent_id, bet_points)

    word_to_guess = start_new_game(word_length)
    challenge_games[opponent_id] = challenge_games[challenger_id] = {
        "word": word_to_guess, 
        "players": {challenger_id, opponent_id}, 
        "history": []
    }

    await callback_query.message.edit_text(f"🆕 Challenge accepted! {word_length}-letter game begins!\n"
                                           "Both players, start guessing the word!")

async def decline_challenge(client, callback_query):
    opponent_id = int(callback_query.data.split("_")[1])
    challenge = challenges.pop(opponent_id, None)

    if challenge:
        await callback_query.message.edit_text("🚫 Challenge declined. No points were deducted.")



async def process_challenge_guess(client, message):
    user_id = message.from_user.id

    if user_id not in challenge_games:
        return

    game_data = challenge_games[user_id]
    word_to_guess = game_data["word"]
    guess = message.text.strip().lower()

    if len(guess) != len(word_to_guess) or not is_valid_english_word(guess):
        return  

    feedback = check_guess(guess, word_to_guess)
    game_data["history"].append(f"{feedback} → {guess.upper()}")

    await message.reply("\n".join(game_data["history"]))

    if guess == word_to_guess:
        winner = user_id
        loser = next(p for p in game_data["players"] if p != winner)

        # Retrieve challenge details safely
        challenge = challenges.get(winner) or challenges.get(loser)
        if not challenge:
            print(f"Error: No challenge found for {winner} or {loser}")
            return

        bet_points = challenge["bet"]

        add_points(winner, bet_points * 2)  

        await message.reply(f"🏆 {message.from_user.first_name} won the challenge!\n"
                            f"🔹 **Winner's new score:** {get_user_score(winner)}\n"
                            f"🔸 **Loser's new score:** {get_user_score(loser)}")

        # Clean up game data
        del group_games[winner]
        del group_games[loser]
        challenges.pop(winner, None)  # Ensure it's deleted safely
        challenges.pop(loser, None)

