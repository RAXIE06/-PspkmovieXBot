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

# Plans Configuration
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

# 1. Plans Menu Command
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
    buttons.append([InlineKeyboardButton("❌ Close", callback_data="close_plan")])
    
    caption = (
        "👑 **PREMIUM MEMBERSHIP PLANS** 👑\n\n"
        "⚡ **Features:**\n"
        "• Direct Files (No Verification / No Ads)\n"
        "• High Speed Download Links\n"
        "• Unlimited Movie Searches\n\n"
        "👇 **Niche diye gaye plans me se select karein:**"
    )
    await message.reply_text(caption, reply_markup=InlineKeyboardMarkup(buttons))

# 2. Plan Select Callback -> QR Code
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
        "days": days,
        "waiting_for_utr": False
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
        f"💳 **Plan:** {days} Days\n"
        f"💰 **Amount:** ₹{amount}\n\n"
        f"📌 **Payment Instructions:**\n"
        f"1. Is QR code ko PhonePe / GPay / Paytm se scan karke exact **₹{amount}** pay karein.\n"
        f"2. Pay karne ke baad receipt se **12-digit UTR** copy karein.\n"
        f"3. Niche **'Submit 12-Digit UTR'** dabakar number send karein."
    )
    
    buttons = [
        [InlineKeyboardButton("✅ Submit 12-Digit UTR", callback_data=f"enter_utr_{user_id}")],
        [InlineKeyboardButton("❌ Cancel", callback_data="close_plan")]
    ]
    
    await callback_query.message.reply_photo(
        photo=bio,
        caption=text,
        reply_markup=InlineKeyboardMarkup(buttons)
    )
    await callback_query.answer()

# 3. UTR prompt handler
@Client.on_callback_query(filters.regex(r"^enter_utr_"))
async def ask_utr_callback(client: Client, callback_query):
    user_id = callback_query.from_user.id
    if user_id not in USER_ORDERS:
        return await callback_query.answer("Pehle /plan select karein!", show_alert=True)
        
    USER_ORDERS[user_id]["waiting_for_utr"] = True
    await callback_query.message.reply_text(
        "✍️ **Apna 12-Digit UTR number message me send karein:**\n(Example: `409823129845`)"
    )
    await callback_query.answer()

# 4. Read UTR and Verify via BharatPe
@Client.on_message(filters.private & filters.text & ~filters.command(["start", "buy", "plan", "help", "myplan"]))
async def utr_checker_msg(client: Client, message: Message):
    user_id = message.from_user.id
    if user_id not in USER_ORDERS or not USER_ORDERS[user_id].get("waiting_for_utr"):
        return

    utr = message.text.strip()
    if not (utr.isdigit() and len(utr) == 12):
        return await message.reply_text("❌ Galat format! UTR sirf 12 digits ka number hona chahiye.")

    if await is_utr_already_used(utr):
        return await message.reply_text("⚠️ Ye UTR pehle hi kisi ne use kar liya hai!")

    status_msg = await message.reply_text("🔄 **BharatPe par verify ho raha hai... Kripya 5 second rukhein.**")
    
    order = USER_ORDERS[user_id]
    expected_amount = order["amount"]
    days = order["days"]
    
    is_valid = await verify_bharatpe(utr, expected_amount)
    
    if is_valid:
        await save_payment_record(user_id=user_id, utr=utr, amount=expected_amount, days=days)
        new_expiry = await add_premium_user(user_id=user_id, days=days)
        del USER_ORDERS[user_id]
        
        await status_msg.edit_text(
            f"🎉 **Payment Verified Successfully!**\n\n"
            f"👑 **Plan Activated:** {days} Days\n"
            f"📅 **Expiry Date:** `{new_expiry.strftime('%d-%m-%Y %H:%M:%S')} UTC`\n\n"
            f"Aapka Premium activate ho chuka hai!"
        )
    else:
        await status_msg.edit_text(
            "❌ **Payment Verify Nahi Hui!**\n\n"
            "• UTR number check karein.\n"
            "• Payment confirm hone me 1 minute lag sakta hai.\n"
            "Thodi der baad dubara try karein."
        )

# 5. Check Active Plan: /myplan
@Client.on_message(filters.command("myplan") & filters.private)
async def myplan_cmd(client: Client, message: Message):
    is_premium, expiry = await check_premium_status(message.from_user.id)
    if is_premium:
        await message.reply_text(
            f"👑 **Aapka Premium Active Hai!**\n\n"
            f"📅 **Expiry Date:** `{expiry.strftime('%d-%m-%Y %H:%M:%S')} UTC`"
        )
    else:
        await message.reply_text("❌ Aapke paas koi active plan nahi hai. /plan dabayein.")

# Close button
@Client.on_callback_query(filters.regex("close_plan"))
async def close_plan_btn(client: Client, callback_query):
    await callback_query.message.delete()

# 6. BharatPe API Call
async def verify_bharatpe(utr: str, expected_amount: float) -> bool:
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
