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

# 2. Plan Select Callback -> Send QR
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
        "waiting_for_utr": True
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
        f"📌 **Instructions:**\n"
        f"1. Is QR code par PhonePe / GPay / Paytm se exact **₹{amount}** pay karein.\n"
        f"2. Pay karne ke baad receipt se **12-digit UTR number** copy karke yahan chat me bhej dein.\n"
        f"*(Agar movie search karni ho to direct movie ka naam likhein ya cancel karein)*"
    )
    
    buttons = [
        [InlineKeyboardButton("❌ Cancel Order", callback_data=f"cancel_order_{user_id}")]
    ]
    
    await callback_query.message.reply_photo(
        photo=bio,
        caption=text,
        reply_markup=InlineKeyboardMarkup(buttons)
    )
    await callback_query.answer()

# Cancel Order Callback
@Client.on_callback_query(filters.regex(r"^cancel_order_"))
async def cancel_order_handler(client: Client, callback_query):
    user_id = callback_query.from_user.id
    if user_id in USER_ORDERS:
        del USER_ORDERS[user_id]
    await callback_query.message.delete()
    await callback_query.answer("Order cancel kar diya gaya hai. Ab aap normally search kar sakte hain!", show_alert=True)

# 3. UTR Listener (Sirf tab chalega jab message 12-digit number ho)
@Client.on_message(filters.private & filters.regex(r"^\d{12}$"))
async def utr_checker_msg(client: Client, message: Message):
    user_id = message.from_user.id
    
    # Agar user ne plan select hi nahi kiya
    if user_id not in USER_ORDERS:
        return
        
    utr = message.text.strip()
    
    if await is_utr_already_used(utr):
        return await message.reply_text("⚠️ Ye UTR pehle hi kisi ne use kar liya hai!")

    status_msg = await message.reply_text("🔄 **BharatPe par verify ho raha hai... 5 second rukhein.**")
    
    order = USER_ORDERS[user_id]
    expected_amount = order["amount"]
    days = order["days"]
    
    is_valid, msg = await verify_bharatpe(utr, expected_amount)
    
    if is_valid:
        await saveYeh dono issues aapke Telegram bot ke **FSM (Finite State Machine / User State)** logic ke galat flow ki wajah se ho rahe hain. 

Jab user `/plan` select karta hai, toh bot user ka state change karke `WAITING_FOR_UTR` (ya payment state) me set kar deta hai. Lekin bot ke paas iss state se bahar nikalne ya state clear karne ka koi timeout ya reset logic nahi hai. Is wajah se har aane wala message (chahe movie ka naam ho ya command) UTR verification handler me hi ja raha hai.

---

### Issue 1: State Stuck & Format Error
* **Karan:** Jab user ne QR generate kiya, user ka state `WAITING_FOR_UTR` set ho gaya. Jab usne movie search karne ke liye text bheja (jaise "Jawan"), bot ne samjha ki yeh UTR number hai. Check me regex fail hua (kyunki movie name 12 digits ka number nahi hota), aur usne bol diya: *"Galat format! UTR sirf 12 digits ka number hona chahiye."*
* **Solution:**
  1. **Cancel Button dein:** QR code ke niche ek inline button lagayein: `❌ Cancel / Back`. Is par click karte hi state clear ho jaye (`await state.clear()` ya `user_states.pop(user_id)`).
  2. **Commands ko state se free karein:** Agar text `/` se start hota hai ya movie query jaisa lagta hai, toh pehle check karein ya commands ko state ke upar priority dein.
  3. **Auto-timeout lagayein:** 10–15 minute baad user ka state automatically clear ho jana chahiye.

---

### Issue 2: Payment ke baad no response & Forever Stuck
* **Karan:** 
  1. Jab aapne 12 digits ka valid UTR bheja, toh bot ne regex format toh pass kar liya, lekin UTR verify karne wale function (API call, database entry, ya admin notification) me koi **unhandled error/exception** aa gaya (jaise API timeout, database column mismatch, ya missing env variable).
  2. Exception aane par code crash ho gaya aur `state.clear()` wali line run hi nahi hui.
  3. State clear na hone ke karan user abhi bhi usi UTR state me fasa hua hai, isliye ab kuch bhi likhne par wahi UTR format error aa raha hai.

---

### Kaise Fix Karein (Code Logic Breakdown)

Agar aap **aiogram** ya **python-telegram-bot** use kar rahe hain, toh flow ko is tarah wrap karein:

#### 1. UTR Handler ke andar `try...except` aur `state.clear()` lagayein:

```python
# aiogram example
@dp.message(PaymentStates.waiting_for_utr)
async def process_utr(message: types.Message, state: FSMContext):
    text = message.text.strip()
    
    # 1. Check agar user ne cancel likha ho ya command di ho
    if text.startswith("/") or text.lower() in ["cancel", "back"]:
        await state.clear()
        await message.answer("Payment process cancel kar diya gaya hai. Ab aap movie search kar sakte hain.")
        return

    # 2. UTR Validation (12 Digits)
    if not (text.isdigit() and len(text) == 12):
        await message.answer("Galat format! UTR sirf 12 digits ka number hona chahiye.\n(Cancel karne ke liye /cancel type karein)")
        return

    # 3. Verification & State Clear
    try:
        # Aapka verification logic / DB check / Admin alert
        is_success = await verify_payment(user_id=message.from_user.id, utr=text)
        
        if is_success:
            await state.clear()  # <-- State clear hona sabse zaroori hai!
            await message.answer("✅ Payment successful! Aapka Premium activate ho gaya hai.")
        else:
            await message.answer("❌ UTR verify nahi ho saka ya pehle use ho chuka hai. Dobara check karein.")
            
    except Exception as e:
        print(f"Error in UTR verification: {e}")
        # Error aane par user ko fasaye mat rakho
        await state.clear() 
        await message.answer("⚠️ Technical issue ki wajah se payment verify nahi ho paya. Admin se contact karein.")
