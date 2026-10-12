import urllib.parse
import random
import asyncio
import datetime
import pytz
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message
from pyrogram.errors import MessageDeleteForbidden
from Script import script
from info import UPI_ID, UPI_NAME, PREMIUM_PLANS, LOG_CHANNEL
from database.users_chats_db import is_utr_used, record_payment, db
from utils import verify_payment_from_email

USER_PLAN_SESSIONS = {}
TIMEZONE = "Asia/Kolkata"

def get_plan_keyboard():
    # Plan ke amount ke hisab se alag-alag premium emojis
    plan_emojis = {
        10: "🍃",
        20: "🏖️",
        40: "⛲",
        55: "🦖",
        75: "🌺",
        200: "🎐",
        270: "🐚",
        399: "🏜️"
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
        await query.message.edit_caption(
            caption=script.HOW_TO_BUY_TXT,
            reply_markup=btn,
            parse_mode=enums.ParseMode.HTML
        )
    except Exception:
        try:
            await query.message.edit_text(
                text=script.HOW_TO_BUY_TXT,
                reply_markup=btn,
                parse_mode=enums.ParseMode.HTML
            )
        except Exception:
            try:
                await query.message.delete()
            except Exception:
                pass
            await client.send_message(
                chat_id=query.message.chat.id,
                text=script.HOW_TO_BUY_TXT,
                reply_markup=btn,
                parse_mode=enums.ParseMode.HTML
            )
    await query.answer()

@Client.on_callback_query(filters.regex(r"^back_to_plans$"))
async def back_to_plans_cb(client: Client, query: CallbackQuery):
    try:
        await query.message.edit_caption(
            caption=script.PREMIUM_TEXT,
            reply_markup=get_plan_keyboard(),
            parse_mode=enums.ParseMode.HTML
        )
    except Exception:
        try:
            await query.message.edit_text(
                text=script.PREMIUM_TEXT,
                reply_markup=get_plan_keyboard(),
                parse_mode=enums.ParseMode.HTML
            )
        except Exception:
            try:
                await query.message.delete()
            except Exception:
                pass
            await client.send_message(
                chat_id=query.message.chat.id,
                text=script.PREMIUM_TEXT,
                reply_markup=get_plan_keyboard(),
                parse_mode=enums.ParseMode.HTML
            )
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

async def auto_verify_loop(client: Client, user_id: int, chat_id: int, qr_msg: Message, exact_amount: float, days: int, mention: str):
    session = USER_PLAN_SESSIONS.get(user_id)
    created_at = session.get("created_at") if session else datetime.datetime.now(pytz.timezone(TIMEZONE))

    # 5 minutes auto check (25 checks x 12 seconds)
    for _ in range(25):
        await asyncio.sleep(12)
        if user_id not in USER_PLAN_SESSIONS:
            return

        is_valid, msg = await verify_payment_from_email(expected_amount=exact_amount, min_time=created_at)
        if is_valid:
            auto_utr = f"AUTO_{exact_amount}_{int(datetime.datetime.now().timestamp())}"
            await record_payment(user_id, auto_utr, exact_amount, days)

            expiry_dt = await db.add_premium_user(user_id, days)
            USER_PLAN_SESSIONS.pop(user_id, None)

            # Auto-delete QR photo immediately on successful payment
            try:
                await qr_msg.delete()
            except Exception:
                pass

            receipt_text = get_success_receipt(mention, user_id, days, expiry_dt)
            await client.send_message(chat_id, receipt_text)

            if LOG_CHANNEL:
                try:
                    await client.send_message(
                        LOG_CHANNEL,
                        f"💎 <b>Auto-Premium Success (Slice Email)</b>\n\n"
                        f"User: {mention} (<code>{user_id}</code>)\n"
                        f"Amount: ₹{exact_amount}\n"
                        f"Days: {days}"
                    )
                except Exception:
                    pass
            return

    # 5 Minutes Timeout: Delete QR and fallback to UTR
    if user_id in USER_PLAN_SESSIONS:
        USER_PLAN_SESSIONS[user_id]["step"] = "WAITING_UTR"
        
        try:
            await qr_msg.delete()
        except Exception:
            pass

        await client.send_message(
            chat_id,
            f"⌛ <b>ᴛɪᴍᴇ ᴜᴘ! ǫʀ ᴄᴏᴅᴇ ᴇxᴘɪʀᴇᴅ</b>\n\n"
            f"💳 <i>ɢᴇɴᴇʀᴀᴛᴇ ᴀ ɴᴇᴡ ᴘᴀʏᴍᴇɴᴛ ǫʀ ᴄᴏᴅᴇ ᴠɪᴀ /plan ᴛᴏ ᴄᴏɴᴛɪɴᴜᴇ.</i>"
        )

@Client.on_callback_query(filters.regex(r"^buyplan_(\d+)"))
async def plan_select_cb(client: Client, query: CallbackQuery):
    base_amount = int(query.data.split("_")[1])
    days = PREMIUM_PLANS.get(base_amount)
    user_id = query.from_user.id
    mention = query.from_user.mention

    # 2 to 15 paise random discount
    discount_paise = random.randint(2, 15) / 100.0
    exact_amount = round(base_amount - discount_paise, 2)

    # Cancel previous task & delete old QR if user switches plans
    if user_id in USER_PLAN_SESSIONS:
        prev_session = USER_PLAN_SESSIONS[user_id]
        if "task" in prev_session and not prev_session["task"].done():
            prev_session["task"].cancel()
        if "qr_msg" in prev_session:
            try:
                await prev_session["qr_msg"].delete()
            except Exception:
                pass

    note = f"Prem_{user_id}"
    upi_url = f"upi://pay?pa={UPI_ID}&pn={urllib.parse.quote(UPI_NAME)}&am={exact_amount:.2f}&cu=INR&tn={note}"
    qr_img = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={urllib.parse.quote(upi_url)}"

    caption = (
        f"⚡ <b>Selected Plan: {days} Days</b>\n"
        f"💵 <b>Original Price:</b> <strike>₹{base_amount}</strike>\n"
        f"🎉 <b>Instant Discount Applied!</b>\n\n"
        f"💰 <b>Pay Exact: ₹{exact_amount}</b>\n\n"
        f"💳 <b>ᴇxᴀᴄᴛ ᴀᴍᴏᴜɴᴛ ɪs ᴘʀᴇsᴇᴛ ɪɴ ᴛʜᴇ ǫʀ</b>\n"
        f"<i>📌 QR sᴄᴀɴ ᴋᴀʀᴋᴇ ᴅɪʏᴀ ɢᴀʏᴀ ᴇxᴀᴄᴛ ᴀᴍᴏᴜɴᴛ ʜɪ ᴘᴀʏ ᴋᴀʀᴇɪɴ.</i>\n\n"
        f"⏳ <b>ǫʀ ᴄᴏᴅᴇ ᴠᴀʟɪᴅɪᴛʏ: 5 ᴍɪɴᴜᴛᴇs</b>\n"
        f"<i>⌛ 5 ᴍɪɴᴜᴛᴇ ʙᴀᴀᴅ ǫʀ ᴄᴏᴅᴇ ᴇxᴘɪʀᴇ ʜᴏ ᴊᴀʏᴇɢᴀ.</i>\n\n"
        f"⚡ <b>ᴀᴜᴛᴏᴍᴀᴛɪᴄ ᴘʀᴇᴍɪᴜᴍ ᴀᴄᴛɪᴠᴀᴛɪᴏɴ</b>\n"
        f"<i>✅ sᴜᴄᴄᴇssғᴜʟ ᴘᴀʏᴍᴇɴᴛ ᴠᴇʀɪғɪᴄᴀᴛɪᴏɴ ᴋᴇ ʙᴀᴀᴅ 10–20 sᴇᴄᴏɴᴅs ᴍᴇɪɴ ᴘʀᴇᴍɪᴜᴍ ᴀᴄᴛɪᴠᴀᴛᴇ ʜᴏ ᴊᴀʏᴇɢᴀ.</i>"
    )

    btn = InlineKeyboardMarkup([
        [InlineKeyboardButton("❓ How to Pay?", callback_data="how_to_buy")],
        [InlineKeyboardButton("🔙 Back to Plans", callback_data="back_to_plans")]
    ])

    qr_msg = await query.message.reply_photo(photo=qr_img, caption=caption, reply_markup=btn)
    await query.answer()

    created_time = datetime.datetime.now(pytz.timezone(TIMEZONE))

    task = asyncio.create_task(
        auto_verify_loop(client, user_id, query.message.chat.id, qr_msg, exact_amount, days, mention)
    )
    
    USER_PLAN_SESSIONS[user_id] = {
        "amount": exact_amount,
        "days": days,
        "step": "AUTO_CHECKING",
        "qr_msg": qr_msg,
        "task": task,
        "created_at": created_time
    }

@Client.on_message(filters.text & filters.private, group=-1)
async def auto_verify_utr_handler(client: Client, message: Message):
    user_id = message.from_user.id
    session = USER_PLAN_SESSIONS.get(user_id)
    if not session:
        return

    text = message.text.strip()
    if message.text.startswith("/"):
        return

    if not text.isdigit() or len(text) < 10:
        return

    utr = text
    if await is_utr_used(utr):
        return await message.reply_text("⚠️ <b>This UTR has already been used / Yeh UTR pehle use ho chuka hai.</b>")

    amount = session["amount"]
    days = session["days"]
    created_at = session.get("created_at")

    wait_msg = await message.reply_text("🔄 <b>Verifying payment... Please wait 10-15 seconds.</b>\n<i>(Payment verify ho raha hai...)</i>")

    is_valid, msg = await verify_payment_from_email(target_utr=utr, min_time=created_at)

    if is_valid:
        await record_payment(user_id, utr, amount, days)
        expiry_dt = await db.add_premium_user(user_id, days)

        USER_PLAN_SESSIONS.pop(user_id, None)

        receipt_text = get_success_receipt(message.from_user.mention, user_id, days, expiry_dt)
        await wait_msg.edit_text(receipt_text)

        if LOG_CHANNEL:
            try:
                await client.send_message(
                    LOG_CHANNEL,
                    f"💎 <b>Fallback UTR Success</b>\n\n"
                    f"User: {message.from_user.mention} (<code>{user_id}</code>)\n"
                    f"Amount: ₹{amount}\n"
                    f"Days: {days}\n"
                    f"UTR: <code>{utr}</code>"
                )
            except Exception:
                pass
    else:
        await wait_msg.edit_text(
            f"❌ <b>Verification Failed / सत्यापन विफल:</b>\n{msg}\n\n"
            f"• <b>English:</b> If amount was debited, try sending UTR again after 1-2 minutes.\n"
            f"• <b>Hinglish:</b> Agar paise kat chuke hain, toh 1-2 minute baad dobara UTR bhejein."
        )
