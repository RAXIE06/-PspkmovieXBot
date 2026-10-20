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
    await sleep(15)  # Bot startup delay
    while True:
        try:
            # UTC time comparison for exact second/minute accuracy
            current_time = datetime.now(pytz.utc)
            
            # MongoDB se sirf wahi users pick honge jinka expiry_time set hai aur time nikal chuka hai
            cursor = db.users.find({
                "expiry_time": {"$ne": None, "$lte": current_time}
            })
            
            async for user in cursor:
                user_id = user.get("id") 
                if not user_id:
                    continue
                
                # Premium access revoke karo
                await db.remove_premium_access(user_id)
                
                try:
                    user_info = await client.get_users(user_id)
                    await client.send_message(
                        chat_id=user_id,
                        text=script.PREMIUM_END_TEXT.format(user_info.mention)
                    )
                    if PREMIUM_LOGS:
                        await client.send_message(
                            PREMIUM_LOGS,
                            text=f"<b>#Premium_Expire\n\nUser name: {user_info.mention}\nUser id: <code>{user_id}</code></b>"
                        )
                except Exception as e:
                    logging.error("Premium expire notification error: %s", e)
                
                await sleep(0.5)
        except Exception as e:
            logging.error(f"Error in check_expired_premium loop: {e}")
            
        await sleep(10)  # Har 10 second me check karega taaki 1min/10min test exact time pe expire ho

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
