import urllib.parse
import random
import asyncio
import datetime
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message
from Script import script
from info import UPI_ID, UPI_NAME, PREMIUM_PLANS, LOG_CHANNEL
from database.users_chats_db import is_utr_used, record_payment, db
from utils import verify_payment_from_email

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

async def auto_verify_loop(client: Client, user_id: int, chat_id: int, exact_amount: float, days: int):
    # 5 minute tak har 12 second me check karega
    for _ in range(25):
        await asyncio.sleep(12)
        if user_id not in USER_PLAN_SESSIONS:
            return

        is_valid, msg = await verify_payment_from_email(expected_amount=exact_amount)
        if is_valid:
            auto_utr = f"AUTO_{exact_amount}_{int(datetime.datetime.now().timestamp())}"
            await record_payment(user_id, auto_utr, exact_amount, days)

            expiry = datetime.date.today() + datetime.timedelta(days=days)
            await db.users.update_one({"id": user_id}, {"$set": {"expiry_time": str(expiry)}}, upsert=True)

            del USER_PLAN_SESSIONS[user_id]

            await client.send_message(
                chat_id,
                f"🎉 <b>Payment Received & Verified!</b>\n\n"
                f"Aapka <b>{days} Days</b> ka Premium activate kar diya gaya hai!\n"
                f"Expiry Date: <code>{expiry}</code>\n\n"
                f"Enjoy unlimited features! 🚀"
            )

            if LOG_CHANNEL:
                try:
                    await client.send_message(
                        LOG_CHANNEL,
                        f"💎 <b>Auto-Premium Success (Slice Email)</b>\n\n"
                        f"User ID: <code>{user_id}</code>\n"
                        f"Amount: ₹{exact_amount}\n"
                        f"Days: {days}\n"
                        f"Status: Auto-Verified"
                    )
                except Exception:
                    pass
            return

    # Timeout fallback
    if user_id in USER_PLAN_SESSIONS:
        USER_PLAN_SESSIONS[user_id]["step"] = "WAITING_UTR"
        await client.send_message(
            chat_id,
            f"⚠️ <b>Auto-verification timeout!</b>\n\n"
            f"Agar aapne <b>₹{exact_amount}</b> pay kar diya hai, toh kripya apna 12-digit <b>UTR / Reference No</b> yahan chat me message karein."
        )

@Client.on_callback_query(filters.regex(r"^buyplan_(\d+)"))
async def plan_select_cb(client: Client, query: CallbackQuery):
    base_amount = int(query.data.split("_")[1])
    days = PREMIUM_PLANS.get(base_amount)
    user_id = query.from_user.id

    # Unique random paise generation taaki ek user dusre se alag ho
    random_paise = random.randint(11, 89) / 100.0
    exact_amount = round(base_amount + random_paise, 2)

    # Cancel previous task if user clicks multiple plans
    if user_id in USER_PLAN_SESSIONS and "task" in USER_PLAN_SESSIONS[user_id]:
        USER_PLAN_SESSIONS[user_id]["task"].cancel()

    note = f"Prem_{user_id}"
    upi_url = f"upi://pay?pa={UPI_ID}&pn={urllib.parse.quote(UPI_NAME)}&am={exact_amount:.2f}&cu=INR&tn={note}"
    qr_img = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={urllib.parse.quote(upi_url)}"

    caption = (
        f"<b>⚡ Selected Plan: ₹{base_amount} ({days} Days)</b>\n\n"
        f"💰 <b>Pay Exact: ₹{exact_amount}</b>\n"
        f"📌 <i>Amount locked hai QR me, bas scan karke pay karein.</i>\n\n"
        f"⚡ <b>Pay karte hi 10-20 second me auto premium unlock ho jayega!</b>"
    )

    btn = InlineKeyboardMarkup([
        [InlineKeyboardButton("❓ Kaise Pay Karein?", callback_data="how_to_buy")],
        [InlineKeyboardButton("🔙 Back to Plans", callback_data="back_to_plans")]
    ])

    await query.message.reply_photo(photo=qr_img, caption=caption, reply_markup=btn)
    await query.answer()

    task = asyncio.create_task(auto_verify_loop(client, user_id, query.message.chat.id, exact_amount, days))
    USER_PLAN_SESSIONS[user_id] = {
        "amount": exact_amount,
        "days": days,
        "step": "AUTO_CHECKING",
        "task": task
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
        return await message.reply_text("⚠️ Ye UTR pehle se hi use ho chuka hai.")

    amount = session["amount"]
    days = session["days"]

    wait_msg = await message.reply_text("🔄 Payment verify ho raha hai, kripya 10-15 seconds wait karein...")

    is_valid, msg = await verify_payment_from_email(target_utr=utr)

    if is_valid:
        await record_payment(user_id, utr, amount, days)
        expiry = datetime.date.today() + datetime.timedelta(days=days)
        await db.users.update_one({"id": user_id}, {"$set": {"expiry_time": str(expiry)}}, upsert=True)

        USER_PLAN_SESSIONS.pop(user_id, None)

        await wait_msg.edit_text(
            f"🎉 <b>UTR Verified Successfully!</b>\n\n"
            f"Aapka <b>{days} Days</b> ka Premium activate kar diya gaya hai!\n"
            f"Expiry Date: <code>{expiry}</code>\n\n"
            f"Enjoy unlimited features!"
        )

        if LOG_CHANNEL:
            try:
                await client.send_message(
                    LOG_CHANNEL,
                    f"💎 <b>Fallback UTR Success</b>\n\n"
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
