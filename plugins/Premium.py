import io
import qrcode
import aiohttp
from datetime import datetime, timedelta

try:
    from pyrogram import Client, filters
    from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
except ImportError:
    from kurigram import Client, filters
    from kurigram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message

from info import BHARATPE_MERCHANT_ID, BHARATPE_TOKEN, BHARATPE_UPI_ID, ADMINS
from database.users_chats_db import (
    add_premium_user,
    check_premium_status,
    is_utr_already_used,
    save_payment_record
)

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

# --- MANUAL ADMIN COMMANDS ---

@Client.on_message(filters.command("add_premium") & filters.user(ADMINS))
async def add_premium_manual(client: Client, message: Message):
    if len(message.command) < 3:
        return await message.reply_text("Usage: `/add_premium <user_id> <days>`")
    try:
        t_user = int(message.command[1])
        days = int(message.command[2])
        new_exp = await add_premium_user(t_user, days)
        await message.reply_text(f"✅ User `{t_user}` ko {days} din ka premium de diya gaya!\nExpiry: `{new_exp}`")
        try:
            await client.send_message(t_user, f"🎉 Admin ne aapka {days} din ka Premium plan activate kar diya hai!")
        except Exception:
            pass
    except Exception as e:
        await message.reply_text(f"Error: {e}")

@Client.on_message(filters.command("myplan") & filters.private)
async def check_my_plan(client: Client, message: Message):
    is_prem, exp = await check_premium_status(message.from_user.id)
    if is_prem:
        await message.reply_text(f"👑 **Premium Active**\n\n📅 Expiry: `{exp.strftime('%d-%m-%Y %H:%M:%S')} UTC`")
    else:
        await message.reply_text("❌ Aapke paas koi active premium plan nahi hai. /plan dabayein.")

# --- AUTOMATIC UPI SYSTEM ---

@Client.on_message(filters.command(["buy", "premium", "plan"]) & filters.private)
async def plan_menu_cmd(client: Client, message: Message):
    buttons = []
    temp_row = []
    for key, data in PLANS.items():
        temp_row.append(InlineKeyboardButton(data["label"], callback_data=f"buy_{key}"))
        if len(temp_row) == 2:
            buttons.append(temp_row)
            temp_row = []
    if temp_row:
        buttons.append(temp_row)
    buttons.append([InlineKeyboardButton("Close", callback_data="close_plan")])
    
    caption = (
        "👑 **PREMIUM MEMBERSHIP PLANS** 👑\n\n"
        "⚡ Direct Files (No Verification / No Ads)\n"
        "🚀 High Speed Download Links\n\n"
        "👇 *Plan select karein:*"
    )
    await message.reply_text(caption, reply_markup=InlineKeyboardMarkup(buttons))

@Client.on_callback_query(filters.regex(r"^buy_"))
async def generate_qr_callback(client: Client, callback_query):
    plan_key = callback_query.data.split("_", 1)[1]
    plan = PLANS.get(plan_key)
    if not plan:
        return await callback_query.answer("Invalid plan!", show_alert=True)
    
    amount = plan["price"]
    days = plan["days"]
    user_id = callback_query.from_user.id
    
    USER_ORDERS[user_id] = {"amount": amount, "days": days}
    
    upi_intent = f"upi://pay?pa={BHARATPE_UPI_ID}&pn=MovieBot&am={amount}&cu=INR&tn=Premium_{user_id}"
    
    qr = qrcode.QRCode(box_size=10, border=2)
    qr.add_data(upi_intent)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    bio = io.BytesIO()
    bio.name = "qr.png"
    img.save(bio, "PNG")
    bio.seek(0)
    
    text = (
        f"💳 **Selected Plan:** {days} Days\n"
        f"💰 **Amount:** ₹{amount}\n\n"
        f"📌 **Step 1:** Kisi bhi UPI app (GPay/PhonePe/Paytm) se exact **₹{amount}** scan karke pay karein.\n"
        f"📌 **Step 2:** Payment ke baad receipt se **12-digit UTR** yahan chat me message karein."
    )
    
    buttons = [[InlineKeyboardButton("Close", callback_data="close_plan")]]
    
    await callback_query.message.reply_photo(photo=bio, caption=text, reply_markup=InlineKeyboardMarkup(buttons))
    await callback_query.answer()

@Client.on_callback_query(filters.regex("close_plan"))
async def close_btn_action(client: Client, callback_query):
    await callback_query.message.delete()

# --- UTR PROCESSOR ---

@Client.on_message(filters.private & filters.regex(r"^\d{12}$"), group=-1)
async def auto_verify_utr(client: Client, message: Message):
    user_id = message.from_user.id
    if user_id not in USER_ORDERS:
        return
        
    message.stop_propagation()
    utr = message.text.strip()
    
    if await is_utr_already_used(utr):
        return await message.reply_text("⚠ Ye UTR pehle hi use ho chuka hai!")
        
    status_msg = await message.reply_text("🔄 **Payment check ho rahi hai... 5 second rukhein.**")
    
    order = USER_ORDERS[user_id]
    amount = order["amount"]
    days = order["days"]
    
    del USER_ORDERS[user_id]
    
    is_valid = await check_bharatpe_status(utr, amount)
    
    if is_valid:
        await save_payment_record(user_id=user_id, utr=utr, amount=amount, days=days)
        new_expiry = await add_premium_user(user_id=user_id, days=days)
        await status_msg.edit_text(
            f"🎉 **Payment Verified Successfully!**\n\n"
            f"👑 **Plan:** {days} Days\n"
            f"📅 **Expiry:** `{new_expiry.strftime('%d-%m-%Y %H:%M:%S')} UTC`"
        )
    else:
        await status_msg.edit_text(
            "❌ **Payment Auto-Verify Nahi Hui!**\n\n"
            f"Agar aapne ₹{amount} pay kar diye hain toh ghabraye nahi, admin ko ye UTR `{utr}` bhej dein, wo turant activate kar denge."
        )

async def check_bharatpe_status(utr: str, expected_amount: float) -> bool:
    url = f"https://merchant.bharatpe.com/api/v1/merchants/{BHARATPE_MERCHANT_ID}/transactions"
    headers = {"token": str(BHARATPE_TOKEN), "User-Agent": "Mozilla/5.0"}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=10) as resp:
                if resp.status != 200:
                    return False
                data = await resp.json()
                for txn in data.get("data", {}).get("transactions", []):
                    t_utr = str(txn.get("bankReferenceNo") or txn.get("utr") or "")
                    t_amt = float(txn.get("amount", 0))
                    status = str(txn.get("status", "")).upper()
                    if t_utr == utr and t_amt == float(expected_amount) and status in ["SUCCESS", "PAID"]:
                        return True
    except Exception:
        pass
    return False
