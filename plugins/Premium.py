import io
import qrcode
import aiohttp
from datetime import datetime

try:
    from pyrogram import Client, filters
    from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
except ImportError:
    from kurigram import Client, filters
    from kurigram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message

from info import BHARATPE_MERCHANT_ID, BHARATPE_TOKEN, BHARATPE_UPI_ID
from database.users_chats_db import (
    add_premium_user,
    check_premium_status,
    is_utr_already_used,
    save_payment_record
)

# Aapke Exact Plans
PLANS = {
    "plan_7": {"days": 7, "price": 10, "label": "◉ 07 ᴅᴀʏꜱ - 10 ₹"},
    "plan_15": {"days": 15, "price": 20, "label": "◉ 15 ᴅᴀʏꜱ - 20 ₹"},
    "plan_30": {"days": 30, "price": 40, "label": "◉ 30 ᴅᴀʏꜱ - 40 ₹"},
    "plan_45": {"days": 45, "price": 55, "label": "◉ 45 ᴅᴀʏꜱ - 55 ₹"},
    "plan_60": {"days": 60, "price": 75, "label": "◉ 60 ᴅᴀʏꜱ - 75 ₹"},
    "plan_180": {"days": 180, "price": 200, "label": "◉ 180 ᴅᴀʏꜱ - 200 ₹"},
    "plan_240": {"days": 240, "price": 270, "label": "◉ 240 ᴅᴀʏꜱ - 270 ₹"},
    "plan_365": {"days": 365, "price": 399, "label": "◉ 365 ᴅᴀʏꜱ - 399 ₹"},
}

USER_ORDERS = {}

# 1. Plans List Command
@Client.on_message(filters.command(["buy", "premium", "plan"]) & filters.private)
async def buy_premium_cmd(client: Client, message: Message):
    buttons = []
    temp_row = []
    for key, data in PLANS.items():
        temp_row.append(InlineKeyboardButton(data["label"], callback_data=f"buy_{key}"))
        if len(temp_row) == 2:
            buttons.append(temp_row)
            temp_row = []
    if temp_row:
        buttons.append(temp_row)
    buttons.append([InlineKeyboardButton("❌ Close", callback_data="closeAapne jo text paste kiya hai, wo ek **ZIP ya compressed archive ka binary/raw dump** lag raha hai jisme files ke naam to dikh rahe hain (jaise `bot.py`, `info.py`, `plugins/`, `database/`, etc.), lekin andar ka source code encrypted ya compressed format (garbage/unreadable text) mein hai. 

Is repository structure se bot ka overview ye hai:

### Repo Overview (`PspkmovieXBot-DreamXBotz`)
Yeh ek **Telegram Auto-Filter / Movie Streaming Bot** ka architecture hai:
* **Core Runtime:** Python 3.12 (`.python-version`), Pyrogram/Telethon framework.
* **Database (`/database`):** MongoDB based file storage (`ia_filterdb.py`), configuration management (`config_db.py`), aur user/chat records (`users_chats_db.py`).
* **Web Server & Fast DL (`/dreamxbotz`):** Aiohttp ya similar web framework jo templates (`dl.html`, `req.html`) ke through direct download links aur fast stream provide karta hai.
* **Deployment Files:** `Dockerfile`, `docker-compose.yml`, `Procfile` (Heroku), `heroku.yml`, aur `app.json`.
* **Plugins (`/plugins`):**
  * `pmfilter.py` & `channel.py`: Inline search, channel file indexing aur button responses.
  * `index.py`: Channel files ko database mein index karna.
  * `Premium.py` & `Redeem.py`: Paid subscription aur referral/redeem system.
  * `commands.py`, `broadcast.py`, `banned.py`: Admin panel aur bot commands.

---

### Aapko kya madad chahiye?
Raw ZIP text ki wajah se actual Python code extract nahi ho sakta. Agar aapko kisi specific file mein kaam karna hai:

1. **Specific file ka code paste kijiye** (jaise `info.py`, `bot.py`, ya `plugins/pmfilter.py`).
2. Ya fir bataiye ki aapko isme **kya edit, fix ya naya feature add** karwana hai?
