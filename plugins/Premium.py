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

async def qr_expiry_task(client: Client, user_id: int, qr_msg: Message):
    """5 min baad QR delete karo — sirf tab jab ye abhi bhi current QR ho."""
    await asyncio.sleep(300)  # 5 minutes

    session = USER_PLAN_SESSIONS.get(user_id)
    if not session:
        return

    # 🔒 Agar user ne naya QR bana liya hai, to purana task chup-chaap return kare
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

@Client.on_callback_query(filters.regex(r"^buyplan_(\d+)"))
async def plan_select_cb(client: Client, query: CallbackQuery):
    base_amount = int(query.data.split("_")[1])
    days = PREMIUM_PLANS.get(base_amount)
    user_id = query.from_user.id
    mention = query.from_user.mention

    # Random discount (2 to 15 paise) — same as before
    discount_paise = random.randint(2, 15) / 100.0
    exact_amount = round(base_amount - discount_paise, 2)

    # Purana QR + session delete karo
    if user_id in USER_PLAN_SESSIONS:
        prev = USER_PLAN_SESSIONS[user_id]
        if "qr_msg" in prev and prev["qr_msg"]:
            try:
                await prev["qr_msg"].delete()
            except Exception:
                pass

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
        f"2️⃣ Slice app kholein\n"
        f"3️⃣ Transaction ka <b>UTR (12 digit)</b> copy karein\n"
        f"4️⃣ Bot ko UTR bhejein\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"⏳ <b>QR Validity:</b> 5 Minutes\n"
        f"⚡ <b>UTR bhejte hi 10-15 sec mein Premium activate ho jayega.</b>"
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
        "step": "WAITING_UTR",
        "qr_msg": qr_msg,
        "created_at": created_time
    }

    # 5 min baad QR + session auto delete
    asyncio.create_task(qr_expiry_task(client, user_id, qr_msg))

@Client.on_message(filters.text & filters.private, group=-1)
async def auto_verify_utr_handler(client: Client, message: Message):
    user_id = message.from_user.id
    session = USER_PLAN_SESSIONS.get(user_id)
    if not session:
        return

    text = message.text.strip()
    if message.text.startswith("/"):
        return

    # UTR = exactly 12 digits
    if not text.isdigit() or len(text) != 12:
        return

    utr = text

    # Duplicate check (courtesy — claim_utr asli atomic check karega)
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

    # UTR + Amount dono match hone chahiye
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
                "👉 Naya QR banane ke liye /plan use karein."
            )

        expiry_dt = await db.add_premium_user(user_id, days)

        # QR delete karo (session pop se pehle qr_msg nikaal lo)
        try:
            if session.get("qr_msg"):
                await session["qr_msg"].delete()
        except Exception:
            pass

        USER_PLAN_SESSIONS.pop(user_id, None)

        receipt_text = get_success_receipt(message.from_user.mention, user_id, days, expiry_dt)
        await wait_msg.edit_text(receipt_text)

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
