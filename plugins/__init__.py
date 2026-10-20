from aiohttp import web
from .route import routes
from asyncio import sleep 
from datetime import datetime
import pytz
from database.users_chats_db import db, ensure_payment_indexes
from info import URL, PREMIUM_LOGS
from Script import script
import aiohttp
import asyncio
import logging

logging.basicConfig(level=logging.INFO)
logging.getLogger("pyrogram").setLevel(logging.ERROR)

async def web_server():
    web_app = web.Application(client_max_size=30000000)
    web_app.add_routes(routes)
    return web_app

async def check_expired_premium(client):
    while True:
        try:
            # 🟢 FIX: UTC time use kiya gaya hai taaki timezone mismatch na ho
            current_time = datetime.now(pytz.utc)
            data = await db.get_expired(current_time)
            
            for user in data:
                user_id = user.get("id") 
                if not user_id:
                    continue
                
                await db.remove_premium_access(user_id)
                try:
                    user_info = await client.get_users(user_id)
                    await client.send_message(
                        chat_id=user_id,
                        text=script.PREMIUM_END_TEXT.format(user_info.mention)
                    )
                    await client.send_message(PREMIUM_LOGS, text=f"<b>#Premium_Expire\n\nUser name: {user_info.mention}\nUser id: <code>{user_id}</code>")
                except Exception as e:
                    logging.error("Premium expire notification error: %s", e)
                await sleep(0.5)
        except Exception as e:
            logging.error(f"Error in check_expired_premium loop: {e}")
            
        await sleep(5) # Har 5 sec baad check karega

async def keep_alive():
    """Keep bot alive by sending periodic pings."""
    async with aiohttp.ClientSession() as session:
        while True:
            await asyncio.sleep(298)
            try:
                async with session.get(URL) as resp:
                    if resp.status != 200:
                        logging.warning(f"⚠️ Ping Error! Status: {resp.status}")
            except Exception as e:
                logging.error(f"❌ Ping Failed: {e}")
