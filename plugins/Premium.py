import urllib.parse
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message
from Script import script
from info import UPI_ID, UPI_NAME, PREMIUM_PLANS, LOG_CHANNEL
from database.users_chats_db import is_utr_used, record_payment
from utils import verify_bharatpe_transaction

USER_PLAN_SESSIONS = {}

def get_plan_keyboard():
    buttons = []
    row = []
    for amount, days in PREMIUM_PLANS.items():
        row.append(InlineKeyboardButton(f"⚡ {days} Days - ₹{amount}", callback_data=f"buyplan_{amount}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton("❓ Premium Kaise Buy Karein?", callback_data="how_to_buy")])
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
    await query.message.edit_text(script.HOW_TO_BUY_TXT, reply_markup=btn)
    await query.answer()

@Client.on_callback_query(filters.regex(r"^back_to_plans$"))
async def back_to_plans_cb(client: Client, query: CallbackQuery):
    await query.message.edit_text(script.PREMIUM_TEXT, reply_markup=get_plan_keyboard())
    await query.answer()

@Client.on_callback_query(filters.regex(r"^buyplan_(\d+)"))
async def plan_select_cb(client: Client, query: CallbackQuery):
    amount = int(query.data.split("_")[1])
    days = PREMIUM_PLANS.get(amount)
    user_id = query.from_user.id

    USER_PLAN_SESSIONS[user_id] = {"amount": amount, "days": days, "step": "WAITING_UTR"}

    note = f"Prem_{user_id}"
    upi_url = f"upi://pay?pa={UPI_ID}&pn={urllib.parse.quote(UPI_NAME)}&am={amount:.2f}&cu=INR&tn={note}"
    qr_img = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={urllib.parse.quote(upi_url)}"

    caption = (
        f"<b>⚡ Selected Plan: ₹{amount} ({days} Days)</b>\n\n"
        f"1. Upar diye gaye <b>QR Code</b> ko scan karke exact <b>₹{amount}</b> pay karein.\n"
        f"2. Pay karne ke baad 12-digit <b>UTR / Transaction Ref No.</b> chat me send karein.\n\n"
        f"<i>⚠️ Galat amount pay na karein.</i>"
    )

    btn = InlineKeyboardMarkup([
        [InlineKeyboardButton("❓ Kaise Pay & UTR Dalein?", callback_data="how_to_buy")],
        [InlineKeyboardButton("🔙 Back to Plans", callback_data="back_to_plans")]
    ])

    await query.message.reply_photo(photo=qr_img, caption=caption, reply_markup=btn)
    await query.answer()

@Client.on_message(filters.text & filters.private, group=-1)
async def auto_verify_utr_handler(client: Client, message: Message):
    user_id = message.from_user.id
    session = USER_PLAN_SESSIONS.get(user_id)
    if not session or session.get("step") != "WAITING_UTR":
        return

    text = message.text.strip()
    if message.text.startswith("/"):
        return

    if not text.isdigit() or len(text) < 10:
        return await message.reply_text("❌ Kripya valid 12-digit UTR number enter karein.")

    utr = text
    if await is_utr_used(utr):
        return await message.reply_text("⚠️ Ye UTR pehle se hi kisi user dwara use kiya ja chuka hai.")

    amount = session["amount"]
    days = session["days"]

    wait_msg = await message.reply_text("🔄 Payment verify ho raha hai, kripya 10-15 seconds wait karein...")

    is_valid, msg = await verify_bharatpe_transaction(utr, amount)

    if is_valid:
        await record_payment(user_id, utr, amount, days)
        
        # Existing bot ke premium activation logic se link
        from database.users_chats_db import db
        import datetime
        expiry = datetime.date.today() + datetime.timedelta(days=days)
        await db.users.update_one({"id": user_id}, {"$set": {"expiry_time": str(expiry)}}, upsert=True)

        del USER_PLAN_SESSIONS[user_id]

        await wait_msg.edit_text(
            f"🎉 <b>Payment Verified Successfully!</b>\n\n"
            f"Aapka <b>{days} Days</b> ka Premium activate kar diya gaya hai!\n"
            f"Expiry Date: <code>{expiry}</code>\n\n"
            f"Enjoy unlimited features!"
        )

        if LOG_CHANNEL:
            try:
                await client.send_message(
                    LOG_CHANNEL,
                    f"💎 <b>Auto-Premium Success</b>\n\n"
                    f"User ID: <code>{user_id}</code>\n"
                    f"Name: {message.from_user.mention}\n"
                    f"Amount: ₹{amount}\n"
                    f"Days: {days}\n"
                    f"UTR: <code>{utr}</code>"
                )
            except Exception:
                pass
    else:
        await wait_msg.edit_text(f"❌ <b>Verification Failed:</b>\n{msg}\n\nAgar paise kat chuke hain toh 1-2 minute baad dubara UTR bhejein.")
