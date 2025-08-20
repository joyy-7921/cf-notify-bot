import time
import requests
import json
import os
from datetime import datetime

# --- Config ---
import os
BOT_TOKEN = os.getenv("BOT_TOKEN")

API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

# --- File to store per-user friends ---
FRIENDS_FILE = "friends_multi.json"

# --- Load database ---
if os.path.exists(FRIENDS_FILE):
    with open(FRIENDS_FILE, "r") as f:
        FRIENDS_DB = json.load(f)
else:
    FRIENDS_DB = {}  # { chat_id: [friends] }

# --- Storage for last statuses per user ---
last_status = {}

def save_friends():
    """Save FRIENDS_DB to file."""
    with open(FRIENDS_FILE, "w") as f:
        json.dump(FRIENDS_DB, f)

def send_telegram_message(chat_id, message, keyboard=False):
    url = f"{API_URL}/sendMessage"
    data = {"chat_id": chat_id, "text": message}
    if keyboard:
        data["reply_markup"] = {
            "keyboard": [
                [{"text": "📊 Status"}, {"text": "✅ Currently Online"}],
                [{"text": "➕ Add Friend"}, {"text": "➖ Remove Friend"}],
                [{"text": "👥 Friends"}]
            ],
            "resize_keyboard": True,
            "one_time_keyboard": False
        }
    requests.post(url, json=data)

def get_status(usernames):
    if not usernames:
        return {}
    url = f"https://codeforces.com/api/user.info?handles={';'.join(usernames)}"
    r = requests.get(url)
    if r.status_code != 200:
        print("Error fetching data:", r.text)
        return {}
    
    data = r.json()
    statuses = {}
    now = int(datetime.now().timestamp())
    for user in data["result"]:
        handle = user["handle"]
        last_online = user["lastOnlineTimeSeconds"]
        statuses[handle] = (now - last_online) < 60
    return statuses

# --- Startup message for you (bot owner) ---
print("🤖 Multi-user bot started! Each Telegram user has their own friends list.")

last_update_id = None

while True:
    try:
        # --- Check updates from Telegram ---
        updates_url = f"{API_URL}/getUpdates"
        params = {"offset": last_update_id + 1 if last_update_id else None, "timeout": 5}
        resp = requests.get(updates_url, params=params).json()

        if "result" in resp:
            for update in resp["result"]:
                last_update_id = update["update_id"]

                if "message" in update:
                    chat_id = str(update["message"]["chat"]["id"])
                    text = update["message"].get("text", "").strip()

                    # Initialize user list if new
                    if chat_id not in FRIENDS_DB:
                        FRIENDS_DB[chat_id] = []
                        save_friends()
                        send_telegram_message(
                            chat_id,
                            "🤖 Welcome! I will track Codeforces friends for you.\n\n"
                            "Use these commands:\n"
                            "• 📊 Status → all friends\n"
                            "• ✅ Currently Online → only online\n"
                            "• ➕ Add Friend → add a handle\n"
                            "• ➖ Remove Friend → remove a handle\n"
                            "• 👥 Friends → show tracked friends",
                            keyboard=True
                        )

                    usernames = FRIENDS_DB[chat_id]

                    # Status
                    if text.lower() in ["status", "📊 status"]:
                        if not usernames:
                            send_telegram_message(chat_id, "⚠️ No friends added yet. Use ➕ Add Friend.")
                        else:
                            lines = [f"{u}: {'ONLINE ✅' if last_status.get(chat_id, {}).get(u, False) else 'OFFLINE ❌'}" for u in usernames]
                            send_telegram_message(chat_id, "📊 Current Status:\n" + "\n".join(lines))

                    # Currently Online
                    elif text.lower() in ["currently online", "✅ currently online"]:
                        online_users = [u for u in usernames if last_status.get(chat_id, {}).get(u, False)]
                        if online_users:
                            send_telegram_message(chat_id, "✅ Currently Online:\n" + "\n".join(online_users))
                        else:
                            send_telegram_message(chat_id, "😴 Nobody is online right now.")

                    # Friends list
                    elif text.lower() in ["friends", "👥 friends"]:
                        if usernames:
                            send_telegram_message(chat_id, "👥 Tracked Friends:\n" + "\n".join(usernames))
                        else:
                            send_telegram_message(chat_id, "⚠️ No friends added yet.")

                    # Add friend
                    elif text.lower().startswith("add ") or text == "➕ Add Friend":
                        handle = text.replace("add", "").replace("➕ Add Friend", "").strip()
                        if handle:
                            if handle not in usernames:
                                usernames.append(handle)
                                save_friends()
                                send_telegram_message(chat_id, f"✅ Added {handle} to your friends list.")
                            else:
                                send_telegram_message(chat_id, f"⚠️ {handle} is already in your list.")
                        elif text == "➕ Add Friend":
                            send_telegram_message(chat_id, "✍️ Send: `add <username>` to add a new friend.")

                    # Remove friend
                    elif text.lower().startswith("remove ") or text == "➖ Remove Friend":
                        handle = text.replace("remove", "").replace("➖ Remove Friend", "").strip()
                        if handle:
                            if handle in usernames:
                                usernames.remove(handle)
                                last_status.get(chat_id, {}).pop(handle, None)
                                save_friends()
                                send_telegram_message(chat_id, f"🗑️ Removed {handle} from your friends list.")
                            else:
                                send_telegram_message(chat_id, f"⚠️ {handle} is not in your list.")
                        elif text == "➖ Remove Friend":
                            send_telegram_message(chat_id, "✍️ Send: `remove <username>` to remove a friend.")

        # --- Check statuses for all users ---
        for chat_id, usernames in FRIENDS_DB.items():
            if not usernames:
                continue
            statuses = get_status(usernames)
            if chat_id not in last_status:
                last_status[chat_id] = {}
            for user, current_status in statuses.items():
                if current_status and not last_status[chat_id].get(user, False):
                    send_telegram_message(chat_id, f"✅ {user} just came ONLINE 🚀 at {datetime.now().strftime('%H:%M:%S')}")
                last_status[chat_id][user] = current_status

    except Exception as e:
        print("Error:", e)

    time.sleep(30)  # check every 30s

