import urllib.parse
import random
import asyncio
import datetime
import pytz
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message
from Script import script
from info import UPI_ID, UPI_NAME, PREMIUM_PLANS, LOG_CHANNEL
from database.users_chats_db import is_utr_used, claim_utr, db
from utils import verify_payment_from_email

USER_PLAN_SESSIONS = {}
TIMEZONE = "Asia/Kolkata"


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


def get_success_receipt(user_mention: str, user_id: int, days: int, exp_dt: datetime.datetime):
    tz = pytz.timezone(TIMEZONE)
    now = datetime.datetime.now(tz)
    
    if isinstance(exp_dt, str):
        try:
            exp_dt = datetime.datetime.strptime(exp_dt[:10], "%Y-%m-%d")
        except Exception:
            exp_dt = now + datetime.timedelta(days=days)
            
    if isinstance(exp_dt, datetime.date) and not isinstance(exp_dt, datetime.datetime):
        exp_dt = datetime.datetime.combine(exp_dt, datetime.time.max)

    exp = exp_dt.astimezone(tz) if getattr(exp_dt, 'tzinfo', None) else tz.localize(exp_dt)
    
    j_date = now.strftime("%d-%m-%Y")
    j_time = now.strftime("%I:%M:%S %p")
    e_date = exp.strftime("%d-%m-%Y")
    e_time = exp.strftime("%I:%M:%S %p")
    
    return (
        f"🎉 <b>ᴘʀᴇᴍɪᴜᴍ ᴀᴅᴅᴇᴅ ꜱᴜᴄᴄᴇꜱꜱꜰᴜʟʟʏ ✅</b>\n\n"
        f"👤 <b>ᴜꜱᴇʀ :</b> {user_mention}\n"
        f"🆔 <b>ᴜꜱᴇʀ ɪᴅ :</b> <code>{user_id}</code>\n"
        f"⚡ <b>ᴘʀᴇᴍɪᴜᴍ ᴀᴄᴄᴇꜱꜱ :</b> {days} Days\n\n"
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
    
    # 🟢 FIX: Agar koi galat amount ka callback aaye to crash na ho
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
