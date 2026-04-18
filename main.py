# main.py (FULL FINAL TRUSTPOSITIF - FITUR LENGKAP)

import asyncio
import logging
from datetime import datetime
import json
import os
import re as _re
from typing import List, Tuple, Dict
import uuid

import pytz
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
import aiohttp

# ================== CONFIG ==================
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [5397964203, 6918801560, 7230912053, 5780186213, 6670157806]

TRUST_BASE = "https://trustpositif.smbgroup.io"
TRUST_LOGIN_URL = TRUST_BASE + "/"
TRUST_CHECK_URL = TRUST_BASE + "/checker"

SESSION_CACHE = {"cookies": None, "last_login": 0}
SESSION_EXPIRE = 300
REQUEST_DELAY = 10
MAX_RETRY = 2

WIB = pytz.timezone("Asia/Jakarta")

CONFIG_FILE = "config.json"
DOMAINS_FILE = "domains.txt"
STATUS_CACHE_FILE = "status_cache.json"

BATCH_SIZE = 30

# ================== LOG ==================
logging.basicConfig(level=logging.INFO)

# ================== BOT ==================
bot = Bot(token=TOKEN, parse_mode="HTML")
dp = Dispatcher(bot)

state = {"target_chat": None, "auto_interval": 0}
domains: List[str] = []
auto_task: asyncio.Task | None = None
shutdown_flag = False

REPORT_STORE: Dict[str, List[Tuple[str, str]]] = {}

# ================== UTIL ==================
def now_wib():
    return datetime.now(WIB).strftime("%d %B %Y • %H:%M WIB")

def clean_domain(s):
    return (s or "").replace("http://","").replace("https://","").split("/")[0]

def looks_like_domain(s):
    return "." in s

# ================== LOGIN ==================
async def login_trustpositif(session):
    payload = {
        "email": os.getenv("LOGIN_EMAIL"),
        "password": os.getenv("LOGIN_PASSWORD")
    }

    async with session.post(TRUST_LOGIN_URL, json=payload) as res:
        if res.status == 200:
            SESSION_CACHE["cookies"] = session.cookie_jar.filter_cookies(TRUST_BASE)
            SESSION_CACHE["last_login"] = asyncio.get_event_loop().time()
            return True
    return False

def is_session_valid():
    if not SESSION_CACHE["cookies"]:
        return False
    return (asyncio.get_event_loop().time() - SESSION_CACHE["last_login"]) < SESSION_EXPIRE

# ================== CHECK ==================
async def cek_trustpositif(domains_in):
    uniq = list(dict.fromkeys(domains_in))[:BATCH_SIZE]

    for _ in range(MAX_RETRY):
        try:
            async with aiohttp.ClientSession() as session:

                if not is_session_valid():
                    ok = await login_trustpositif(session)
                    if not ok:
                        continue
                else:
                    session.cookie_jar.update_cookies(SESSION_CACHE["cookies"])

                await asyncio.sleep(REQUEST_DELAY)

                async with session.post(TRUST_CHECK_URL, json={"domains": uniq}) as res:
                    if res.status != 200:
                        continue
                    data = await res.json()

                result = []
                for item in data:
                    d = clean_domain(item.get("domain"))
                    s = str(item.get("status","")).lower()

                    if "nawala" in s or "blokir" in s or "blocked" in s:
                        result.append((d,"BLOKIR"))
                    else:
                        result.append((d,"AMAN"))

                return result

        except:
            await asyncio.sleep(2)

    return [(d,"ERROR") for d in uniq]

async def cek_semua_dalam_batch(ds):
    hasil = []
    for batch in [ds[i:i+BATCH_SIZE] for i in range(0,len(ds),BATCH_SIZE)]:
        hasil += await cek_trustpositif(batch)
    return hasil

# ================== FORMAT ==================
def format_result(rows):
    text = f"📊 <b>HASIL CEK</b>\n🕒 {now_wib()}\n\n"
    for d,s in rows:
        icon = "✅" if s=="AMAN" else "🟥" if s=="BLOKIR" else "🟨"
        text += f"{icon} {d} | {s}\n"
    return text

# ================== HANDLER ==================
def is_admin(uid): return uid in ADMIN_IDS

@dp.message_handler(commands=["cek"])
async def cek_cmd(msg: types.Message):
    if not is_admin(msg.from_user.id): return
    args = msg.get_args().split()
    res = await cek_semua_dalam_batch(args)
    await msg.reply(format_result(res))

@dp.message_handler(content_types=["text"])
async def paste(msg: types.Message):
    if not is_admin(msg.from_user.id): return
    if msg.text.startswith("/"): return
    items=[]
    for l in msg.text.splitlines(): items+=l.split()
    res = await cek_semua_dalam_batch(items)
    await msg.reply(format_result(res))

# ================== AUTO ==================
async def auto_loop():
    while True:
        if domains:
            res = await cek_semua_dalam_batch(domains)
            if state["target_chat"]:
                await bot.send_message(state["target_chat"], format_result(res))
        await asyncio.sleep(state["auto_interval"]*60)

@dp.message_handler(commands=["auto"])
async def auto_cmd(msg: types.Message):
    if not is_admin(msg.from_user.id): return
    menit=int(msg.get_args() or 5)
    state["auto_interval"]=menit
    asyncio.create_task(auto_loop())
    await msg.reply(f"Auto ON {menit} menit")

# ================== RUN ==================
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
