import urllib.parse
import random
import asyncio
import datetime
import re
import logging
import pytz
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message
from Script import script
from info import UPI_ID, UPI_NAME, PREMIUM_PLANS, LOG_CHANNEL, ADMINS
from database.users_chats_db import is_utr_used, claim_utr, db
from utils import verify_payment_from_email

logger = logging.getLogger(__name__)

USER_PLAN_SESSIONS = {}
TIMEZONE = "Asia/Kolkata"


def parse_duration(time_str: str):
    time_str = time_str.lower().strip()
    match = re.match(r"^(\d+)\s*(min|m|minute|minutes|h|hour|hours|d|day|days|month|months|y|year|years)$", time_str)
    if not match:
        return None
    
    val = int(match.group(1))
    unit = match.group(2)

    if unit in ("min", "m", "minute", "minutes"):
        return datetime.timedelta(minutes=val)
    elif unit in ("h", "hour", "hours"):
        return datetime.timedelta(hours=val)
    elif unit in ("d", "day", "days"):
        return datetime.timedelta(days=val)
    elif unit in ("month", "months"):
        return datetime.timedelta(days=val * 30)
    elif unit in ("y", "year", "years"):
        return datetime.timedelta(days=val * 365)
    return None


def get_plan_keyboard():
    plan_emojis = {
        10: "🍃", 20: "🏖️", 40: "⛲", 55: "🦖",
        75: "🌺", 200: "🎐", 270: "🐚", 399: "🏜️"
    }
    buttons = []
    row = []
    for amount, days in PREMIUM_PLANS.items():
        emoji = plan_emojis.get(amount, "⚡")
        row.append(InlineKeyboardButton(f"{emoji} {days} Days - ₹{amount}", callback_data=f"buyplan_{amount}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton("💎 𝖧𝗈𝗐 𝗍𝗈 𝖡𝗎𝗒 𝖯𝗋𝖾𝗆𝗂𝗎𝗆❓", callback_data="how_to_buy")])
    buttons.append([InlineKeyboardButton("❌ Close", callback_data="close_data")])
    return InlineKeyboardMarkup(buttons)


@Client.on_message(filters.command(["plan", "premium"]) & filters.private)
async def plans_cmd(client: Client, message: Message):
    await message.reply_text(
        text=script.PREMIUM_TEXT,
        reply_markup=get_plan_keyboard()
    )


@Client.on_callback_query(filters.regex(r"^how_to_buy$"))
async def how_to_buy_cb(client: Client, query: CallbackQuery):
    btn = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Plans", callback_data="back_to_plans")]])
    try:
        await query.message.edit_caption(caption=script.HOW_TO_BUY_TXT, reply_markup=btn, parse_mode=enums.ParseMode.HTML)
    except Exception:
        try:
            await query.message.edit_text(text=script.HOW_TO_BUY_TXT, reply_markup=btn, parse_mode=enums.ParseMode.HTML)
        except Exception:
            try:
                await query.message.delete()
            except Exception:
                pass
            await client.send_message(chat_id=query.message.chat.id, text=script.HOW_TO_BUY_TXT, reply_markup=btn, parse_mode=enums.ParseMode.HTML)
    await query.answer()


@Client.on_callback_query(filters.regex(r"^back_to_plans$"))
async def back_to_plans_cb(client: Client, query: CallbackQuery):
    try:
        await query.message.edit_caption(caption=script.PREMIUM_TEXT, reply_markup=get_plan_keyboard(), parse_mode=enums.ParseMode.HTML)
    except Exception:
        try:
            await query.message.edit_text(text=script.PREMIUM_TEXT, reply_markup=get_plan_keyboard(), parse_mode=enums.ParseMode.HTML)
        except Exception:
            try:
                await query.message.delete()
            except Exception:
                pass
            await client.send_message(chat_id=query.message.chat.id, text=script.PREMIUM_TEXT, reply_markup=get_plan_keyboard(), parse_mode=enums.ParseMode.HTML)
    await query.answer()


def get_success_receipt(user_mention: str, user_id: int, duration_info, exp_dt: datetime.datetime):
    tz = pytz.timezone(TIMEZONE)
    now = datetime.datetime.now(tz)
    
    if isinstance(exp_dt, str):
        try:
            exp_dt = datetime.datetime.fromisoformat(exp_dt)
        except Exception:
            try:
                exp_dt = datetime.datetime.strptime(exp_dt, "%Y-%m-%d %H:%M:%S")
            except Exception:
                exp_dt = now

    if isinstance(exp_dt, datetime.date) and not isinstance(exp_dt, datetime.datetime):
        exp_dt = datetime.datetime.combine(exp_dt, datetime.time.max)

    exp = exp_dt.astimezone(tz) if getattr(exp_dt, 'tzinfo', None) else tz.localize(exp_dt)
    
    j_date = now.strftime("%d-%m-%Y")
    j_time = now.strftime("%I:%M:%S %p")
    e_date = exp.strftime("%d-%m-%Y")
    e_time = exp.strftime("%I:%M:%S %p")
    
    duration_str = f"{duration_info} Days" if isinstance(duration_info, int) else str(duration_info)
    
    return (
        f"🎉 <b>ᴘʀᴇᴍɪᴜᴍ ᴀᴅᴅᴇᴅ ꜱᴜᴄᴄᴇꜱꜱꜰᴜʟʟYY ✅</b>\n\n"
        f"👤 <b>ᴜꜱᴇʀ :</b> {user_mention}\n"
        f"🆔 <b>ᴜꜱᴇʀ ɪᴅ :</b> <code>{user_id}</code>\n"
        f"⚡ <b>ᴘʀᴇᴍɪᴜᴍ ᴀᴄᴄᴇꜱꜱ :</b> {duration_str}\n\n"
        f"📅 <b>ᴊᴏɪɴɪɴɢ ᴅᴀᴛᴇ :</b> <code>{j_date}</code>\n"
        f"⏰ <b>ᴊᴏɪɴɪɴɢ ᴛɪᴍᴇ :</b> <code>{j_time}</code>\n\n"
        f"⏳ <b>ᴇxᴘɪʀʏ ᴅᴀᴛᴇ :</b> <code>{e_date}</code>\n"
        f"⏰ <b>ᴇxᴘɪʀʏ ᴛɪᴍᴇ :</b> <code>{e_time}</code>\n\n"
        f"🚀 <i>Enjoy unlimited direct downloads without shorteners, force-subs, or ads!</i>"
    )


# ==================== HELPERS ==================== #

def get_active_amounts(exclude_user_id=None):
    amounts = set()
    for uid, sess in USER_PLAN_SESSIONS.items():
        if exclude_user_id is not None and uid == exclude_user_id:
            continue
        if sess.get("step") in ("AUTO_CHECKING", "WAITING_UTR_CONFIRM"):
            amt = sess.get("amount")
            if amt is not None:
                amounts.add(round(amt, 2))
    return amounts


def get_users_with_amount(amount, exclude_user_id=None):
    amount = round(amount, 2)
    users = []
    for uid, sess in USER_PLAN_SESSIONS.items():
        if exclude_user_id is not None and uid == exclude_user_id:
            continue
        if sess.get("step") in ("AUTO_CHECKING", "WAITING_UTR_CONFIRM"):
            if sess.get("amount") is not None and round(sess["amount"], 2) == amount:
                users.append(uid)
    return users


async def qr_expiry_task(client: Client, user_id: int, qr_msg: Message):
    await asyncio.sleep(300)

    session = USER_PLAN_SESSIONS.get(user_id)
    if not session:
        return

    current_qr = session.get("qr_msg")
    if current_qr is None or getattr(current_qr, "id", None) != qr_msg.id:
        return

    USER_PLAN_SESSIONS.pop(user_id, None)

    try:
        await qr_msg.delete()
    except Exception:
        pass

    try:
        await client.send_message(
            user_id,
            "⌛ <b>ǫʀ ᴄᴏᴅᴇ ᴇxᴘɪʀᴇᴅ!</b>\n\n"
            "💳 <i>Naya QR banane ke liye /plan command use karein.</i>"
        )
    except Exception:
        pass


# ==================== AUTO VERIFY LOOP ==================== #

async def auto_verify_loop(client: Client, user_id: int, qr_msg: Message, exact_amount: float, days: int, mention: str):
    session = USER_PLAN_SESSIONS.get(user_id)
    if not session:
        return
    created_at = session["created_at"]

    for _ in range(25):
        await asyncio.sleep(12)

        session = USER_PLAN_SESSIONS.get(user_id)
        if not session:
            return
        if session.get("step") != "AUTO_CHECKING":
            return

        is_valid, result = await verify_payment_from_email(
            expected_amount=exact_amount,
            min_time=created_at
        )
        if not is_valid:
            continue

        others = get_users_with_amount(exact_amount, exclude_user_id=user_id)

        if not others:
            real_utr = str(result).strip()
            claimed = await claim_utr(user_id, real_utr, exact_amount, days)
            if not claimed:
                USER_PLAN_SESSIONS.pop(user_id, None)
                try:
                    await client.send_message(
                        user_id,
                        "⚠️ <b>Ye payment already use ho chuka hai.</b>\n\n"
                        "👉 /plan se naya QR banayein."
                    )
                except Exception:
                    pass
                return

            expiry_dt = await db.add_premium_user(user_id, days)

            try:
                if qr_msg:
                    await qr_msg.delete()
            except Exception:
                pass

            USER_PLAN_SESSIONS.pop(user_id, None)

            receipt = get_success_receipt(mention, user_id, days, expiry_dt)
            try:
                await client.send_message(user_id, receipt)
            except Exception:
                pass

            if LOG_CHANNEL:
                try:
                    await client.send_message(
                        LOG_CHANNEL,
                        f"💎 <b>Auto-Premium Success</b>\n\n"
                        f"User: {mention} (<code>{user_id}</code>)\n"
                        f"Amount: ₹{exact_amount}\n"
                        f"Days: {days}\n"
                        f"UTR: <code>{real_utr}</code>"
                    )
                except Exception:
                    pass
            return

        collision_users = [user_id] + others
        for uid in collision_users:
            sess = USER_PLAN_SESSIONS.get(uid)
            if not sess:
                continue
            if sess.get("step") == "WAITING_UTR_CONFIRM":
                continue
            sess["step"] = "WAITING_UTR_CONFIRM"
            try:
                await client.send_message(
                    uid,
                    f"⚠️ <b>ᴘᴀʏᴍᴇɴᴛ ʀᴇᴄᴇɪᴠᴇᴅ!</b>\n\n"
                    f"💰 <b>Amount:</b> <code>₹{exact_amount}</code>\n\n"
                    f"Is amount pe 2 users hain. Confirm karne ke liye apna "
                    f"<b>12-digit UTR</b> bhejein.\n\n"
                    f"<i>Jo pehle sahi UTR bhejega, usko Premium milega.</i>\n\n"
                    f"📍 <b>UTR kaha milega?</b>\n"
                    f"Slice app → Transaction → Copy UTR"
                )
            except Exception:
                pass
        return


# ==================== PLAN SELECT ==================== #

@Client.on_callback_query(filters.regex(r"^buyplan_(\d+)"))
async def plan_select_cb(client: Client, query: CallbackQuery):
    base_amount = int(query.data.split("_")[1])
    days = PREMIUM_PLANS.get(base_amount)
    
    if days is None:
        return await query.answer("❌ Invalid Plan Selected!", show_alert=True)

    user_id = query.from_user.id
    mention = query.from_user.mention

    if user_id in USER_PLAN_SESSIONS:
        prev = USER_PLAN_SESSIONS[user_id]
        if prev.get("qr_msg"):
            try:
                await prev["qr_msg"].delete()
            except Exception:
                pass

    used = get_active_amounts(exclude_user_id=user_id)
    exact_amount = None
    for _ in range(500):
        d = random.randint(1, 99)
        c = round(base_amount - d / 100.0, 2)
        if c < 9.0:
            continue
        if c in used:
            continue
        exact_amount = c
        break

    if exact_amount is None:
        exact_amount = round(max(9.0, base_amount - random.randint(1, 99) / 100.0), 2)

    note = f"Prem_{user_id}"
    upi_url = f"upi://pay?pa={UPI_ID}&pn={urllib.parse.quote(UPI_NAME)}&am={exact_amount:.2f}&cu=INR&tn={note}"
    qr_img = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={urllib.parse.quote(upi_url)}"

    caption = (
        f"⚡ <b>Selected Plan:</b> {days} Days\n"
        f"💵 <b>Original Price:</b> <strike>₹{base_amount}</strike>\n"
        f"🎉 <b>Instant Discount Applied!</b>\n\n"
        f"💰 <b>Pay Exact:</b> <code>₹{exact_amount}</code>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📌 <b>ᴘᴀʏᴍᴇɴᴛ ꜱᴛᴇᴘꜱ :</b>\n\n"
        f"1️⃣ QR scan karke <b>₹{exact_amount}</b> pay karein\n"
        f"2️⃣ Bas itna hi — Premium auto-activate ho jayega\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"⏳ <b>QR Validity:</b> 5 Minutes\n"
        f"⚡ <b>Payment ke 10-20 sec mein Premium milega.</b>"
    )

    btn = InlineKeyboardMarkup([
        [InlineKeyboardButton("❓ How to Pay?", callback_data="how_to_buy")],
        [InlineKeyboardButton("🔙 Back to Plans", callback_data="back_to_plans")]
    ])

    qr_msg = await query.message.reply_photo(photo=qr_img, caption=caption, reply_markup=btn)
    await query.answer()

    created_time = datetime.datetime.now(pytz.timezone(TIMEZONE))

    USER_PLAN_SESSIONS[user_id] = {
        "amount": exact_amount,
        "days": days,
        "step": "AUTO_CHECKING",
        "qr_msg": qr_msg,
        "created_at": created_time,
    }

    asyncio.create_task(auto_verify_loop(client, user_id, qr_msg, exact_amount, days, mention))
    asyncio.create_task(qr_expiry_task(client, user_id, qr_msg))


# ==================== UTR FALLBACK / COLLISION HANDLER ==================== #

@Client.on_message(filters.text & filters.private, group=-1)
async def utr_handler(client: Client, message: Message):
    user_id = message.from_user.id
    session = USER_PLAN_SESSIONS.get(user_id)
    if not session:
        return

    text = message.text.strip()
    if message.text.startswith("/"):
        return

    if not text.isdigit() or len(text) != 12:
        return

    step = session.get("step")
    if step not in ("AUTO_CHECKING", "WAITING_UTR", "WAITING_UTR_CONFIRM"):
        return

    utr = text

    if await is_utr_used(utr):
        return await message.reply_text(
            "⚠️ <b>Yeh UTR pehle use ho chuka hai!</b>\n\n"
            "👉 Naya QR banane ke liye /plan command use karein."
        )

    amount = session["amount"]
    days = session["days"]
    created_at = session.get("created_at")

    wait_msg = await message.reply_text(
        "🔄 <b>Verifying UTR...</b>\n"
        "<i>Please wait 10-15 seconds.</i>"
    )

    is_valid, msg = await verify_payment_from_email(
        target_utr=utr,
        expected_amount=amount,
        min_time=created_at
    )

    if is_valid:
        claimed = await claim_utr(user_id, utr, amount, days)
        if not claimed:
            USER_PLAN_SESSIONS.pop(user_id, None)
            return await wait_msg.edit_text(
                "⚠️ <b>Yeh UTR abhi-abhi kisi aur ne use kar liya.</b>\n\n"
                "Aapka Premium nahi mil sakta. /plan se naya QR banayein."
            )

        expiry_dt = await db.add_premium_user(user_id, days)

        try:
            if session.get("qr_msg"):
                await session["qr_msg"].delete()
        except Exception:
            pass

        USER_PLAN_SESSIONS.pop(user_id, None)

        receipt = get_success_receipt(message.from_user.mention, user_id, days, expiry_dt)
        await wait_msg.edit_text(receipt)

        if LOG_CHANNEL:
            try:
                await client.send_message(
                    LOG_CHANNEL,
                    f"💎 <b>UTR Premium Success</b>\n\n"
                    f"User: {message.from_user.mention} (<code>{user_id}</code>)\n"
                    f"Amount: ₹{amount}\n"
                    f"Days: {days}\n"
                    f"UTR: <code>{utr}</code>"
                )
            except Exception:
                pass
    else:
        await wait_msg.edit_text(
            f"❌ <b>ᴜᴛʀ ᴠᴇʀɪꜰʏ ɴᴀʜɪ ʜᴜᴀ</b>\n\n"
            f"<i>Agar payment kar diye hain to</i> "
            f"<a href='https://t.me/Owner_helpbot'>@Owner_helpbot</a> "
            f"<i>support team se baat kar lein.</i>\n\n"
            f"<b>Possible reasons:</b>\n"
            f"• Payment abhi process ho raha hai (1-2 min wait karein)\n"
            f"• UTR galat copy hua hai\n"
            f"• Payment fail ho gaya"
        )


# ==================== MANUAL TESTING & CHECK COMMANDS ==================== #

@Client.on_message(filters.command(["add_premium", "give_premium"]) & filters.user(ADMINS))
async def add_premium_cmd(client: Client, message: Message):
    if len(message.command) < 3:
        return await message.reply_text(
            "<b>Usage:</b>\n"
            "<code>/add_premium user_id time</code>\n\n"
            "<b>Examples:</b>\n"
            "• <code>/add_premium 123456789 1min</code> (Testing ke liye)\n"
            "• <code>/add_premium 123456789 10min</code>\n"
            "• <code>/add_premium 123456789 1d</code>"
        )

    try:
        user_id = int(message.command[1])
    except ValueError:
        return await message.reply_text("❌ Invalid User ID!")

    duration_str = message.command[2]
    time_delta = parse_duration(duration_str)

    if not time_delta:
        return await message.reply_text("❌ Invalid format! Use: <code>1min</code>, <code>10min</code>, <code>1h</code>, <code>1d</code>")

    try:
        expiry = await db.add_premium_user(user_id, time_delta)
        tz = pytz.timezone(TIMEZONE)
        exp_ist = expiry.astimezone(tz) if getattr(expiry, 'tzinfo', None) else tz.localize(expiry)
        formatted_expiry = exp_ist.strftime("%d-%b-%Y %I:%M:%S %p")
        
        await message.reply_text(
            f"✅ <b>Premium Added!</b>\n\n"
            f"👤 <b>User ID:</b> <code>{user_id}</code>\n"
            f"⏳ <b>Duration:</b> <code>{duration_str}</code>\n"
            f"📅 <b>Expires At:</b> <code>{formatted_expiry} (IST)</code>"
        )

        try:
            await client.send_message(
                chat_id=user_id,
                text=(
                    f"🎉 <b>Premium Activated!</b>\n\n"
                    f"⏳ <b>Validity:</b> <code>{duration_str}</code>\n"
                    f"📅 <b>Expires:</b> <code>{formatted_expiry} (IST)</code>"
                )
            )
        except Exception:
            pass

    except Exception as e:
        logger.error(f"Error in add_premium_cmd: {e}")
        await message.reply_text(f"❌ Error: {e}")


@Client.on_message(filters.command(["remove_premium", "del_premium"]) & filters.user(ADMINS))
async def remove_premium_cmd(client: Client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("<b>Usage:</b> <code>/remove_premium user_id</code>")

    try:
        user_id = int(message.command[1])
        await db.remove_premium_access(user_id)
        await message.reply_text(f"✅ Removed premium from <code>{user_id}</code>.")
        try:
            await client.send_message(user_id, "⚠️ <b>Your premium subscription has been removed by admin.</b>")
        except Exception:
            pass
    except Exception as e:
        await message.reply_text(f"❌ Error: {e}")


@Client.on_message(filters.command("myplan") & filters.private)
async def myplan_cmd(client: Client, message: Message):
    user_id = message.from_user.id
    has_access = await db.has_premium_access(user_id)
    user = await db.get_user(user_id)

    if not has_access or not user or not user.get("expiry_time"):
        return await message.reply_text(
            "❌ <b>You don't have an active premium plan.</b>\n\n"
            "Use /plan to buy premium access!"
        )

    exp_dt = user["expiry_time"]
    tz = pytz.timezone(TIMEZONE)
    now = datetime.datetime.now(tz)
    
    if isinstance(exp_dt, str):
        try:
            exp_dt = datetime.datetime.fromisoformat(exp_dt)
        except Exception:
            exp_dt = now

    if isinstance(exp_dt, datetime.date) and not isinstance(exp_dt, datetime.datetime):
        exp_dt = datetime.datetime.combine(exp_dt, datetime.time.max)

    exp = exp_dt.astimezone(tz) if getattr(exp_dt, 'tzinfo', None) else tz.localize(exp_dt)
    
    remaining = exp - now
    if remaining.total_seconds() <= 0:
        await db.remove_premium_access(user_id)
        return await message.reply_text("⚠️ <b>Your premium plan has just expired!</b>")

    mins, secs = divmod(int(remaining.total_seconds()), 60)
    hours, mins = divmod(mins, 60)
    days, hours = divmod(hours, 24)

    rem_str = f"{days}d {hours}h {mins}m {secs}s" if days > 0 else f"{hours}h {mins}m {secs}s"
    formatted_expiry = exp.strftime("%d-%b-%Y %I:%M:%S %p")

    await message.reply_text(
        f"👑 <b>Your Premium Subscription Status:</b>\n\n"
        f"✅ <b>Status:</b> <code>Active</code>\n"
        f"⏳ <b>Time Remaining:</b> <code>{rem_str}</code>\n"
        f"📅 <b>Expiry:</b> <code>{formatted_expiry} (IST)</code>"
    )


# ==================== ACTIVE PREMIUM USERS LIST (FIXED) ==================== #

@Client.on_message(filters.command(["premium_users", "active_users"]) & filters.user(ADMINS))
async def premium_users_list_cmd(client: Client, message: Message):
    wait_msg = await message.reply_text("⏳ <b>Fetching active premium users list...</b>")
    
    tz = pytz.timezone(TIMEZONE)
    now_utc = datetime.datetime.now(pytz.utc)
    now_ist = datetime.datetime.now(tz)

    try:
        cursor = db.users.find({
            "expiry_time": {"$ne": None, "$gt": now_utc}
        }).sort("expiry_time", 1)

        users_list = []
        async for doc in cursor:
            users_list.append(doc)

        if not users_list:
            return await wait_msg.edit_text("❌ <b>Koi bhi active premium user nahi mila.</b>")

        text = f"<b>ᴘʀᴇᴍɪᴜᴍ ᴜꜱᴇʀꜱ ʟɪꜱᴛ ({len(users_list)}) :</b>\n\n"

        for i, user in enumerate(users_list, 1):
            u_id = user.get("id")
            exp_dt = user.get("expiry_time")
            user_name = user.get("name") or f"User <code>{u_id}</code>"

            try:
                tg_user = await asyncio.wait_for(client.get_users(u_id), timeout=1.5)
                user_name = tg_user.mention
            except Exception:
                pass

            if isinstance(exp_dt, str):
                try:
                    exp_dt = datetime.datetime.fromisoformat(exp_dt)
                except Exception:
                    try:
                        exp_dt = datetime.datetime.strptime(exp_dt, "%Y-%m-%d %H:%M:%S")
                    except Exception:
                        exp_dt = now_utc

            if isinstance(exp_dt, datetime.date) and not isinstance(exp_dt, datetime.datetime):
                exp_dt = datetime.datetime.combine(exp_dt, datetime.time.max)

            exp_ist = exp_dt.astimezone(tz) if getattr(exp_dt, 'tzinfo', None) else tz.localize(exp_dt)

            e_date = exp_ist.strftime("%d-%m-%Y")
            e_time = exp_ist.strftime("%I:%M:%S %p")

            remaining = exp_ist - now_ist
            if remaining.total_seconds() > 0:
                total_seconds = int(remaining.total_seconds())
                days, rem_sec = divmod(total_seconds, 86400)
                hours, rem_sec = divmod(rem_sec, 3600)
                minutes, _ = divmod(rem_sec, 60)

                time_parts = []
                if days > 0:
                    time_parts.append(f"{days} days")
                if hours > 0:
                    time_parts.append(f"{hours} hours")
                time_parts.append(f"{minutes} minutes")
                time_left = ", ".join(time_parts) if time_parts else "less than 1 minute"
            else:
                time_left = "Expired"

            text += (
                f"<b>{i}. {user_name}</b>\n"
                f" ᴜꜱᴇʀ ɪᴅ : <code>{u_id}</code>\n"
                f" ᴇxᴘɪʀʏ ᴅᴀᴛᴇ : <code>{e_date}</code>\n"
                f" ᴇxᴘɪʀʏ ᴛɪᴍᴇ : <code>{e_time}</code>\n"
                f" ᴛɪᴍᴇ ʟᴇꜰᴛ : <code>{time_left}</code>\n\n"
            )

        if len(text) > 4096:
            for chunk in [text[j:j+4000] for j in range(0, len(text), 4000)]:
                await message.reply_text(chunk)
            await wait_msg.delete()
        else:
            await wait_msg.edit_text(text)

    except Exception as e:
        logger.error(f"Error fetching premium users: {e}")
        await wait_msg.edit_text(f"❌ <b>Error fetching list:</b> <code>{e}</code>")


# ==================== AUTO-EXPIRY BACKGROUND WORKER ==================== #

async def auto_premium_expiry_worker(client: Client):
    await asyncio.sleep(15)
    logger.info("Auto-Premium Expiry Background Worker Started.")
    while True:
        try:
            now_utc = datetime.datetime.now(pytz.utc)
            cursor = db.users.find({
                "expiry_time": {"$ne": None, "$lte": now_utc}
            })

            async for user in cursor:
                u_id = user["id"]
                await db.remove_premium_access(u_id)
                logger.info(f"Premium expired automatically for user {u_id}")

                try:
                    await client.send_message(
                        chat_id=u_id,
                        text=(
                            "⚠️ <b>Your Premium Plan Has Expired!</b>\n\n"
                            "Aapka subscription period poora ho gaya hai. Services resume karne ke liye /plan se recharge karein."
                        )
                    )
                except Exception:
                    pass

        except Exception as e:
            logger.error(f"Error in auto_premium_expiry_worker: {e}")

        await asyncio.sleep(30)
