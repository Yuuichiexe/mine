from pymongo import MongoClient, ASCENDING, DESCENDING

# MongoDB Connection
DATABASE_URL = "mongodb+srv://Apple:music@cluster0.sijq9.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
client = MongoClient(DATABASE_URL)
mongo_db = client["word_test"]
db = mongo_db

# Collections
global_scores = db["global_scores"]
chat_scores = db["chat_scores"]
usersdb = db["users"]
chatsdb = db["chats"]

# Ensure Indexes for Performance
global_scores.create_index([("score", DESCENDING)])
chat_scores.create_index([("chat_id", ASCENDING), ("score", DESCENDING)])


# ** User Management **  
def is_served_user(user_id: int) -> bool:
    return usersdb.find_one({"user_id": user_id}) is not None

def get_served_users() -> list:
    return [user["user_id"] for user in usersdb.find({}, {"_id": 0, "user_id": 1})]

def add_served_user(user_id: int):
    if not is_served_user(user_id):
        usersdb.insert_one({"user_id": user_id})
        print(f"🆕 New User Added: {user_id}")  # ✅ Print user ID when added

# ** Chat Management **  
def is_served_chat(chat_id: int) -> bool:
    return chatsdb.find_one({"chat_id": chat_id}) is not None

def get_served_chats() -> list:
    return [chat["chat_id"] for chat in chatsdb.find({}, {"_id": 0, "chat_id": 1})]

def add_served_chat(chat_id: int):
    if not is_served_chat(chat_id):
        chatsdb.insert_one({"chat_id": chat_id})
        print(f"🆕 New Chat Added: {chat_id}")  # ✅ Print chat ID when added


# Users Global and chat scores 

def get_user_score(user_id):
    user = global_scores.find_one({"user_id": user_id}, {"_id": 0, "score": 1})
    return user["score"] if user else 0  # Default to 0 if user not found

def get_chat_user_score(chat_id, user_id):
    user = chat_scores.find_one({"chat_id": chat_id, "user_id": user_id}, {"_id": 0, "score": 1})
    return user["score"] if user else 0  # Default to 0 if user not found

def add_points(user_id, points):
    global_scores.update_one(
        {"user_id": user_id},
        {"$inc": {"score": points}},
        upsert=True  # Create if user doesn't exist
    )

def deduct_points(user_id, points):
    current_score = get_user_score(user_id)
    new_score = max(0, current_score - points)  # Prevent negative points
    global_scores.update_one(
        {"user_id": user_id},
        {"$set": {"score": new_score}}
    )

# Update global score
def update_global_score(user_id, points=1):
    add_points(user_id, points)  # This function now handles global score updates

# Get user balance (alias of get_user_score)
def get_user_balance(user_id):
    return get_user_score(user_id)

def update_chat_score(chat_id, user_id, points=1):
    chat_scores.update_one(
        {"chat_id": chat_id, "user_id": user_id},
        {"$inc": {"score": points}},
        upsert=True
    )

def deduct_chat_points(chat_id, user_id, points):
    current_score = get_chat_user_score(chat_id, user_id)
    new_score = max(0, current_score - points)  # Prevent negative points
    chat_scores.update_one(
        {"chat_id": chat_id, "user_id": user_id},
        {"$set": {"score": new_score}}
    )


def get_user_points(user_id):  
    return get_user_score(user_id)

def update_user_points(user_id, chat_id, points):
    if points > 0:
        add_points(user_id, points)  # Global leaderboard update
        update_chat_score(chat_id, user_id, points)  # Chat leaderboard update
    else:
        deduct_points(user_id, abs(points))  # Global leaderboard update
        deduct_chat_points(chat_id, user_id, abs(points))  
        
#  Leaderboard and Score Management 
def update_global_score(user_id: int, points: int = 1):
    global_scores.update_one(
        {"user_id": user_id},
        {"$inc": {"score": points}},
        upsert=True
    )
    updated_user = global_scores.find_one({"user_id": user_id})
    print(f"Updated Global Score: {updated_user}")  # Debugging output

def update_chat_score(chat_id: int, user_id: int, points: int = 1):
    chat_scores.update_one(
        {"chat_id": chat_id, "user_id": user_id},
        {"$inc": {"score": points}},
        upsert=True
    )
    updated_user = chat_scores.find_one({"chat_id": chat_id, "user_id": user_id})
    print(f"Updated Chat Score: {updated_user}")  # Debugging output


def get_global_leaderboard():
    leaderboard = list(mongo_db.global_scores.find({}, {"user_id": 1, "score": 1}))
    leaderboard = sorted(leaderboard, key=lambda x: x["score"], reverse=True)  # Ensure sorting
    return [(entry["user_id"], entry["score"]) for entry in leaderboard]  # Return correct format


def get_chat_leaderboard(chat_id):
    """Retrieve the chat-specific leaderboard sorted by score."""
    leaderboard = list(
        mongo_db.chat_scores.find({"chat_id": chat_id}, {"user_id": 1, "score": 1}).sort("score", -1)
    )
    return leaderboard

# ** Debugging: Fetch and Print Leaderboards **
