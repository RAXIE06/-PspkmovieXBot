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
    buttons.append([InlineKeyboardButton("Close", callback_data="close_plan")])
    
    caption = (
        "👑 **PREMIUM MEMBERSHIP PLANS** 👑\n\n"
        "⚡ **Features:**\n"
        "• Direct Files (No Verification / No Ads)\n"
        "• High Speed Download Links\n"
        "• Unlimited Movie Searches\n\n"
        "👇 **Niche diye gaye plans me se select karein:**"
    )
    await message.reply_text(caption, reply_markup=InlineKeyboardMarkup(buttons))

# 2. Plan Select Callback -> Dynamic QR Code
@Client.on_callback_query(filters.regex(r"^buy_"))
async def send_qr_handler(client: Client, callback_query):
    plan_key = callback_query.data.split("_", 1)[1]
    plan = PLANS.get(plan_key)
    if not plan:
        return await callback_query.answer("Invalid plan!", show_alert=True)
    
    amount = plan["price"]
    days = plan["days"]
    user_id = callback_query.from_user.id
    
    USER_ORDERS[user_id] = {
        "amount": amount,
        "days": days
    }
    
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
        f"📌 **Payment Instructions:**\n"
        f"1. Is QR code par PhonePe / GPay / Paytm se exact **₹{amount}** pay karein.\n"
        f"2. Pay karne ke baad receipt se **12-digit UTR** number chat me bhej dein.\n"
        f"*(Aap bina cancel kare direct movie ka naam bhi search kar sakte hain)*"
    )
    
    buttons = [
        [InlineKeyboardButton("Close", callback_data="close_plan")]
    ]
    
    await callback_query.message.reply_photo(
        photo=bio,
        caption=text,
        reply_markup=InlineKeyboardMarkup(buttons)
    )
    await callback_query.answer()

# 3. UTR Listener (Sirf tab chalega jab message sirf 12-digit number ho)
@Client.on_message(filters.private & filters.regex(r"^\d{12}$"))
async def utr_checker_msg(client: Client, message: Message):
    user_id = message.from_user.id
    
    # Agar user ne plan select hi nahi kiya, normal text ki tarah ignore karo
    if user_id not in USER_ORDERS:
        return

    utr = message.text.strip()
    
    if await is_utr_already_used(utr):
        return await message.reply_text("⚠️️ Ye UTR pehle hi use ho chuka hai!")

    status_msg = await message.reply_text("🔄 **Payment verify ho rahi hai... 5 second rukhein.**")
    
    order = USER_ORDERS[user_id]
    expected_amount = order["amount"]
    days = order["days"]
    
    is_valid = await check_bharatpe_payment(utr, expected_amount)
    
    # State se user ko free kar do taaki koi lock na rahe
    del USER_ORDERS[user_id]
    
    if is_valid:
        await save_payment_record(user_id=user_id, utr=utr, amount=expected_amount, days=days)
        new_expiry = await add_premium_user(user_id=user_id, days=days)
        
        await status_msg.edit_text(
            f"🎉 **Payment Verified Successfully!**\n\n"
            f"👑 **Plan Activated:** {days} Days\n"
            f"📅 **Expiry:** `{new_expiry.strftime('%d-%m-%Y %H:%M:%S')} UTC`\n\n"
            f"Aapka Premium activate ho gaya hai! Ab bina ads ke direct enjoy karein."
        )
    else:
        await status_msg.edit_text(
            "❌ **Payment Verify Nahi Hui!**\n\n"
            "• UTR number check karein.\n"
            "• Payment confirm hone me 1 minute lag sakta hai.\n"
            "Agar pay kar diya hai toh 1 minute baad dubara 12-digit UTR send karein."
        )

# 4. Check Plan Command: /myplan
@Client.on_message(filters.command("myplan") & filters.private)
async def myplan_cmd(client: Client, message: Message):
    is_premium, expiry = await check_premium_status(message.from_user.id)
    if is_premium:
        await message.reply_text(
            f"👑 **Aapka Premium Active Hai!**\n\n"
            f"📅 **Expiry Date:** `{expiry.strftime('%d-%m-%Y %H:%M:%S')} UTC`"
        )
    else:
        await message.reply_text("❌ Aapke paas koi active plan nahi hai. /plan dabakar buy karein.")

# Close button handler
@Client.on_callback_query(filters.regex("close_plan"))
async def close_plan_btn(client: Client, callback_query):
    await callback_query.message.delete()

# 5. BharatPe Verification Call
async def check_bharatpe_payment(utr: str, expected_amount: float) -> bool:
    url = f"https://merchant.bharatpe.com/api/v1/merchants/{BHARATPE_MERCHANT_ID}/transactions"
    headers = {
        "token": BHARATPE_TOKEN,
        "User-Agent": "Mozilla/5.0"
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=15) as resp:
                if resp.status != 200:
                    return False
                data = await resp.json()
                transactions = data.get("data", {}).get("transactions", [])
                for txn in transactions:
                    txn_utr = str(txn.get("bankReferenceNo") or txn.get("utr") or "")
                    txn_amount = float(txn.get("amount", 0))
                    status = txn.get("status", "").upper()
                    
                    if txn_utr == utr and txn_amount == float(expected_amount) and status in ["SUCCESS", "PAID"]:
                        return True
    except Exception as e:
        print(f"Error checking BharatPe: {e}")
    return False
