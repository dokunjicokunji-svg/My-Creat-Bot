# =============================================
# PowerPointBreak Bot v19 (Full Unified Edition)
# Systems: (1) Post Countdown  (2) Auto Scheduler  (3) Giveaway
# Extras: Signature + Owner Control + Replit Keep-Alive
# =============================================

# --- Keep Alive for Replit (UptimeRobot) ---
from keep_alive import keep_alive
keep_alive()

import os, asyncio, sqlite3, re, random, math
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatType
from telegram.ext import (
    Application, ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
)

# -------------------- CONFIG --------------------
# Token: env var -> fallback to provided token
BOT_TOKEN = os.getenv("BOT_TOKEN") or "8393089794:AAEltGzYfmtxL6NbNK9ey4ISl7sRh-pSB1A"
CHANNEL_USERNAME = "@PowerPointBreak"
GROUP_USERNAME   = "@PowerPointBreakConversion"
OWNER_TAG        = "@MinexxProo"

TZ = ZoneInfo("Asia/Dhaka")
DB = "ppb_allinone.db"

# Progress bar (global style; System-1 & System-3 reuse)
PROGRESS_BLOCKS = 12
PROGRESS_FILLED = "▰"
PROGRESS_EMPTY  = "▱"

# Public participant count mode (System-3)
PUBLIC_COUNT_MODE = "boosted"  # "real" or "boosted"

# -------------------- DB INIT --------------------
def db():
    conn = sqlite3.connect(DB, check_same_thread=False)

    # S1: Live Countdown Posts
    conn.execute("""
    CREATE TABLE IF NOT EXISTS live_posts(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id INTEGER NOT NULL,
        msg_id INTEGER NOT NULL,
        end_ts INTEGER NOT NULL,
        title TEXT,
        prize TEXT,
        status TEXT DEFAULT 'running' -- running|done
    );
    """)

    # S2: Scheduler
    conn.execute("""
    CREATE TABLE IF NOT EXISTS schedules(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        target_chat_id INTEGER NOT NULL,
        post_text TEXT NOT NULL,
        fire_ts INTEGER NOT NULL,
        status TEXT DEFAULT 'pending' -- pending|fired
    );
    """)

    # S3: Giveaway
    conn.execute("""
    CREATE TABLE IF NOT EXISTS giveaways(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id INTEGER NOT NULL,
        msg_id INTEGER NOT NULL,
        prize TEXT,
        end_ts INTEGER,
        max_entries INTEGER,
        winner_count INTEGER DEFAULT 3,
        status TEXT DEFAULT 'running' -- running|awaiting|done
    );
    """)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS participants(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        giveaway_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        username TEXT,
        name TEXT,
        joined_ts INTEGER,
        UNIQUE(giveaway_id, user_id)
    );
    """)

    # S3 settings
    conn.execute("""
    CREATE TABLE IF NOT EXISTS gw_settings(
        chat_id TEXT PRIMARY KEY,
        verify_chan1 TEXT,
        verify_chan2 TEXT,
        autowinner INTEGER DEFAULT 0
    );
    """)

    # Global signature/owner
    conn.execute("""
    CREATE TABLE IF NOT EXISTS global_settings(
        chat_id TEXT PRIMARY KEY,
        signature_on INTEGER DEFAULT 1,
        owner_tag TEXT DEFAULT ?
    );
    """, (OWNER_TAG,))
    conn.commit()
    return conn

# -------------------- HELPERS --------------------
def is_admin_id_list(admins):
    return [a.user.id for a in admins]

async def is_admin_or_owner(update: Update) -> bool:
    chat = update.effective_chat
    user = update.effective_user
    if chat.type == ChatType.PRIVATE:
        return True
    try:
        admins = await chat.get_administrators()
        return user.id in is_admin_id_list(admins)
    except Exception:
        return False

def parse_time_str(s: str):
    from datetime import datetime as _dt
    for fmt in ("%I:%M %p", "%H:%M"):
        try:
            t = _dt.strptime(s.upper(), fmt)
            return t.hour, t.minute
        except:
            pass
    raise ValueError("Bad time format")

def fmt_dur(sec:int)->str:
    if sec < 0: sec = 0
    h = sec // 3600; m = (sec % 3600)//60; s = sec % 60
    return f"{h}h {m}m {s}s"

def make_bar(total:int, left:int, blocks:int=PROGRESS_BLOCKS, filled:str=PROGRESS_FILLED, empty:str=PROGRESS_EMPTY)->str:
    if total <= 0: total = 1
    done = max(0, total - max(0,left))
    fb = int(blocks * done / total); fb = max(0, min(blocks, fb))
    return filled*fb + empty*(blocks - fb)

def signature_footer(chat_id:int)->str:
    # read signature setting per-chat
    with db() as c:
        row = c.execute("SELECT signature_on, owner_tag FROM global_settings WHERE chat_id=?", (str(chat_id),)).fetchone()
        if not row:
            c.execute("INSERT INTO global_settings(chat_id,signature_on,owner_tag) VALUES(?,?,?)",
                      (str(chat_id), 1, OWNER_TAG))
            sig_on, owner = 1, OWNER_TAG
        else:
            sig_on, owner = row
    if not sig_on: return ""
    return "\n━━━━━━━━━━━━━━━━━━\n📢 Powered by PowerPointBreak\n👤 Owner: " + (owner or OWNER_TAG)

def display_count(real:int)->int:
    if PUBLIC_COUNT_MODE == "real":
        return real
    # boosted mapping
    if real == 0: return 0
    if real == 1: return 3
    if real <= 5: return 7
    if real <= 10: return 14
    return int(math.ceil(real*1.2))

# -------------------- BASIC / META COMMANDS --------------------
async def cmd_start(update:Update, context:ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 PowerPointBreak Bot v19 (Full Unified)\n"
        "✅ Systems Loaded: Countdown • Scheduler • Giveaway\n"
        "Use /allcd to see all commands."
    )

async def cmd_allcd(update:Update, context:ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📜 ALL COMMANDS\n\n"
        "System-1 (Post Countdown)\n"
        "/livepost \"Title\" \"Prize\" 11:30 PM\n"
        "/changetime 11:45 PM\n"
        "/extendtime +10m  (or +1h/+30s)\n\n"
        "System-2 (Auto Scheduler)\n"
        "/schedulepost <chat_id> \"YYYY-MM-DD HH:MM\" \"\"\"message\"\"\"\n\n"
        "System-3 (Giveaway)\n"
        "/setverify @chan1 @chan2\n"
        "/gw \"Prize\" 10x 9:00 PM\n"
        "/winnercount <n>\n"
        "/autowinner on|off\n"
        "/winnerstatus\n"
        "/selectwinner\n"
        "/joinedlist\n\n"
        "Signature & Owner\n"
        "/setsignature on|off\n"
        "/viewsignature\n"
        "/setowner @NewOwner\n"
        "/ownerinfo"
    )

# -------------------- OWNER / SIGNATURE --------------------
async def cmd_setsignature(update:Update, context:ContextTypes.DEFAULT_TYPE):
    if not await is_admin_or_owner(update): return
    if not context.args or context.args[0].lower() not in ("on","off"):
        return await update.message.reply_text("Usage: /setsignature on|off")
    on = 1 if context.args[0].lower()=="on" else 0
    with db() as c:
        row = c.execute("SELECT chat_id FROM global_settings WHERE chat_id=?", (str(update.effective_chat.id),)).fetchone()
        if row:
            c.execute("UPDATE global_settings SET signature_on=? WHERE chat_id=?", (on, str(update.effective_chat.id)))
        else:
            c.execute("INSERT INTO global_settings(chat_id,signature_on,owner_tag) VALUES(?,?,?)",
                      (str(update.effective_chat.id), on, OWNER_TAG))
    await update.message.reply_text(f"✅ Signature: {'ON' if on else 'OFF'}")

async def cmd_viewsignature(update:Update, context:ContextTypes.DEFAULT_TYPE):
    with db() as c:
        row = c.execute("SELECT signature_on,owner_tag FROM global_settings WHERE chat_id=?", (str(update.effective_chat.id),)).fetchone()
    if not row: return await update.message.reply_text(f"ℹ️ Signature: ON\n👤 Owner: {OWNER_TAG}")
    await update.message.reply_text(f"ℹ️ Signature: {'ON' if row[0] else 'OFF'}\n👤 Owner: {row[1] or OWNER_TAG}")

async def cmd_setowner(update:Update, context:ContextTypes.DEFAULT_TYPE):
    if not await is_admin_or_owner(update): return
    if not context.args or not context.args[0].startswith("@"):
        return await update.message.reply_text("Usage: /setowner @NewOwner")
    with db() as c:
        row = c.execute("SELECT chat_id FROM global_settings WHERE chat_id=?", (str(update.effective_chat.id),)).fetchone()
        if row:
            c.execute("UPDATE global_settings SET owner_tag=? WHERE chat_id=?", (context.args[0], str(update.effective_chat.id)))
        else:
            c.execute("INSERT INTO global_settings(chat_id,signature_on,owner_tag) VALUES(?,?,?)",
                      (str(update.effective_chat.id), 1, context.args[0]))
    await update.message.reply_text(f"✅ Owner updated to {context.args[0]}")

async def cmd_ownerinfo(update:Update, context:ContextTypes.DEFAULT_TYPE):
    with db() as c:
        row = c.execute("SELECT signature_on,owner_tag FROM global_settings WHERE chat_id=?", (str(update.effective_chat.id),)).fetchone()
    on = row[0] if row else 1; owner = row[1] if row else OWNER_TAG
    await update.message.reply_text(f"👤 Owner: {owner}\n🧩 Signature: {'ON' if on else 'OFF'}")

# -------------------- SYSTEM-1: POST COUNTDOWN --------------------
async def cmd_livepost(update:Update, context:ContextTypes.DEFAULT_TYPE):
    if not await is_admin_or_owner(update): return
    text = update.message.text
    try:
        a1 = text.index('"'); b1 = text.index('"', a1+1)
        a2 = text.index('"', b1+1); b2 = text.index('"', a2+1)
        title = text[a1+1:b1]; prize = text[a2+1:b2]
        tstr  = text[b2+1:].strip()
    except Exception:
        return await update.message.reply_text('Usage:\n/livepost "Title" "Prize" 11:30 PM')
    try:
        H,M = parse_time_str(tstr)
    except:
        return await update.message.reply_text("❌ Bad time. Example: 11:30 PM or 23:30")

    now = datetime.now(TZ)
    end = now.replace(hour=H,minute=M,second=0,microsecond=0)
    if end<=now: end += timedelta(days=1)
    total = int((end-now).total_seconds())

    bar = make_bar(total,total)
    body = (
        "🎉💥 MEGA POST LIVE! 💥🎉\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"📝 {title}\n"
        f"🏆 Prize: {prize}\n"
        f"🕒 Ends: {end.strftime('%I:%M %p')}\n\n"
        f"⏳ Left: {fmt_dur(total)}\n"
        f"{bar}\n"
        "🟢 Countdown started"
        + signature_footer(update.effective_chat.id)
    )
    msg = await update.message.reply_text(body)

    with db() as c:
        c.execute("INSERT INTO live_posts(chat_id,msg_id,end_ts,title,prize,status) VALUES(?,?,?,?,?,?)",
                  (update.effective_chat.id, msg.message_id, int(end.timestamp()), title, prize, "running"))

    asyncio.create_task(s1_loop(msg.chat_id, msg.message_id))

async def s1_loop(chat_id:int, msg_id:int):
    while True:
        with db() as c:
            row = c.execute("SELECT id,end_ts,title,prize,status FROM live_posts WHERE chat_id=? AND msg_id=?",
                            (chat_id, msg_id)).fetchone()
        if not row: break
        _id, end_ts, title, prize, status = row
        if status != "running": break

        now = int(datetime.now(TZ).timestamp())
        left = end_ts - now
        if left <= 0:
            try:
                await application.bot.edit_message_text(
                    chat_id=chat_id, message_id=msg_id,
                    text=(f"🏁 Countdown Ended!\n🎯 {title}\n✅ Time over.") + signature_footer(chat_id)
                )
            except: pass
            with db() as c:
                c.execute("UPDATE live_posts SET status='done' WHERE id=?", (_id,))
            break

        total = max(1, end_ts - now)
        bar = make_bar(total, left)
        body = (
            "🎉💥 MEGA POST LIVE! 💥🎉\n"
            "━━━━━━━━━━━━━━━━━━\n"
            f"📝 {title}\n"
            f"🏆 Prize: {prize}\n"
            f"🕒 Ends: {datetime.fromtimestamp(end_ts,TZ).strftime('%I:%M %p')}\n\n"
            f"⏳ Left: {fmt_dur(left)}\n"
            f"{bar}\n"
            "🟢 Countdown started"
            + signature_footer(chat_id)
        )
        try:
            await application.bot.edit_message_text(chat_id=chat_id, message_id=msg_id, text=body)
        except: pass
        await asyncio.sleep(1)

async def cmd_changetime(update:Update, context:ContextTypes.DEFAULT_TYPE):
    if not await is_admin_or_owner(update): return
    tstr = update.message.text.partition(" ")[2].strip()
    if not tstr: return await update.message.reply_text("Usage: /changetime 11:45 PM")
    try:
        H,M = parse_time_str(tstr)
    except:
        return await update.message.reply_text("❌ Bad time.")
    with db() as c:
        row = c.execute("SELECT id FROM live_posts WHERE chat_id=? AND status='running' ORDER BY id DESC LIMIT 1",
                        (update.effective_chat.id,)).fetchone()
    if not row: return await update.message.reply_text("❗ No running livepost found.")
    _id = row[0]
    now = datetime.now(TZ)
    end = now.replace(hour=H,minute=M,second=0,microsecond=0)
    if end<=now: end += timedelta(days=1)
    with db() as c:
        c.execute("UPDATE live_posts SET end_ts=? WHERE id=?", (int(end.timestamp()), _id))
    await update.message.reply_text(f"✅ End time changed to {end.strftime('%I:%M %p')}")

async def cmd_extendtime(update:Update, context:ContextTypes.DEFAULT_TYPE):
    if not await is_admin_or_owner(update): return
    arg = update.message.text.partition(" ")[2].strip()
    m = re.fullmatch(r"\+(\d+)([hms])", arg or "")
    if not m: return await update.message.reply_text("Usage: /extendtime +10m | +1h | +30s")
    val, unit = int(m.group(1)), m.group(2)
    add = {"h":3600,"m":60,"s":1}[unit] * val
    with db() as c:
        row = c.execute("SELECT id,end_ts FROM live_posts WHERE chat_id=? AND status='running' ORDER BY id DESC LIMIT 1",
                        (update.effective_chat.id,)).fetchone()
    if not row: return await update.message.reply_text("❗ No running livepost found.")
    _id, end_ts = row
    with db() as c:
        c.execute("UPDATE live_posts SET end_ts=? WHERE id=?", (end_ts+add, _id))
    await update.message.reply_text(f"⏫ Extended by {val}{unit}.")

# -------------------- SYSTEM-2: AUTO SCHEDULER --------------------
async def cmd_schedulepost(update:Update, context:ContextTypes.DEFAULT_TYPE):
    if not await is_admin_or_owner(update): return
    text = update.message.text
    m = re.search(r'/schedulepost\s+(-?\d+)\s+"([^"]+)"\s+"""([\s\S]+)"""', text)
    if not m:
        return await update.message.reply_text('Usage:\n/schedulepost <chat_id> "YYYY-MM-DD HH:MM" """message"""')
    target = int(m.group(1)); when_str = m.group(2); msg = m.group(3)
    try:
        dt = datetime.strptime(when_str, "%Y-%m-%d %H:%M").replace(tzinfo=TZ)
    except:
        return await update.message.reply_text("❌ Time must be YYYY-MM-DD HH:MM (24h).")
    with db() as c:
        c.execute("INSERT INTO schedules(target_chat_id,post_text,fire_ts,status) VALUES(?,?,?,?)",
                  (target, msg, int(dt.timestamp()), "pending"))
    await update.message.reply_text(f"✅ Scheduled for {dt.strftime('%Y-%m-%d %H:%M')} → chat {target}")

async def scheduler_loop(app):
    while True:
        try:
            now_ts = int(datetime.now(TZ).timestamp())
            with db() as c:
                rows = c.execute("SELECT id,target_chat_id,post_text FROM schedules WHERE status='pending' AND fire_ts<=?",
                                 (now_ts,)).fetchall()
            for _id, target, text in rows:
                try:
                    await app.bot.send_message(chat_id=target, text=text + signature_footer(target))
                    with db() as c:
                        c.execute("UPDATE schedules SET status='fired' WHERE id=?", (_id,))
                except Exception:
                    pass
        except Exception:
            pass
        await asyncio.sleep(10)

# -------------------- SYSTEM-3: GIVEAWAY --------------------
def get_verify_channels(chat_id:int):
    with db() as c:
        row = c.execute("SELECT verify_chan1,verify_chan2 FROM gw_settings WHERE chat_id=?", (str(chat_id),)).fetchone()
        return (row[0], row[1]) if row else (None, None)

def set_verify_channels(chat_id:int, c1:str, c2:str):
    with db() as c:
        row = c.execute("SELECT autowinner FROM gw_settings WHERE chat_id=?", (str(chat_id),)).fetchone()
        aw = row[0] if row else 0
        c.execute("INSERT OR REPLACE INTO gw_settings(chat_id,verify_chan1,verify_chan2,autowinner) VALUES(?,?,?,?)",
                  (str(chat_id), c1, c2, aw))

def get_autowinner(chat_id:int)->int:
    with db() as c:
        row = c.execute("SELECT autowinner FROM gw_settings WHERE chat_id=?", (str(chat_id),)).fetchone()
        return row[0] if row else 0

def set_autowinner(chat_id:int, on:int):
    with db() as c:
        row = c.execute("SELECT verify_chan1,verify_chan2 FROM gw_settings WHERE chat_id=?", (str(chat_id),)).fetchone()
        c1,c2 = (row[0],row[1]) if row else (None,None)
        c.execute("INSERT OR REPLACE INTO gw_settings(chat_id,verify_chan1,verify_chan2,autowinner) VALUES(?,?,?,?)",
                  (str(chat_id), c1, c2, 1 if on else 0))

def gw_controls_markup(gw_id:int)->InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("🎉 Participate Now", callback_data=f"GW:join:{gw_id}")]])

def gw_insert(chat_id:int, msg_id:int, prize:str, end_ts:int, max_entries:int, winner_count:int)->int:
    with db() as c:
        cur = c.execute(
            "INSERT INTO giveaways(chat_id,msg_id,prize,end_ts,max_entries,winner_count,status) VALUES(?,?,?,?,?,?,?)",
            (chat_id,msg_id,prize,end_ts,max_entries,winner_count,'running')
        )
        return cur.lastrowid

def gw_get(gw_id:int):
    with db() as c:
        return c.execute("SELECT id,chat_id,msg_id,prize,end_ts,max_entries,winner_count,status FROM giveaways WHERE id=?",(gw_id,)).fetchone()

def gw_get_active(chat_id:int):
    with db() as c:
        return c.execute("SELECT id,chat_id,msg_id,prize,end_ts,max_entries,winner_count,status FROM giveaways WHERE chat_id=? AND status IN ('running','awaiting') ORDER BY id DESC LIMIT 1",(chat_id,)).fetchone()

def add_participant(gw_id:int, user_id:int, username:str, name:str)->bool:
    now_ts = int(datetime.now(TZ).timestamp())
    with db() as c:
        try:
            c.execute("INSERT INTO participants(giveaway_id,user_id,username,name,joined_ts) VALUES(?,?,?,?,?)",
                      (gw_id, user_id, username, name, now_ts))
            return True
        except sqlite3.IntegrityError:
            return False

def count_part(gw_id:int)->int:
    with db() as c:
        r = c.execute("SELECT COUNT(*) FROM participants WHERE giveaway_id=?", (gw_id,)).fetchone()
        return r[0] if r else 0

def list_parts(gw_id:int):
    with db() as c:
        return c.execute("SELECT user_id,username,name FROM participants WHERE giveaway_id=? ORDER BY joined_ts",(gw_id,)).fetchall()

def pick_winners(gw_id:int, k:int):
    rows = list_parts(gw_id)
    pool = [(r[0],r[1],r[2]) for r in rows if r[0]]
    if not pool: return []
    random.shuffle(pool)
    return pool[:k]

async def inchat_verify_loading(chat_id:int, reply_to:int, context:ContextTypes.DEFAULT_TYPE):
    try:
        msg = await context.bot.send_message(chat_id=chat_id, reply_to_message_id=reply_to,
            text="🔍 Verifying your membership...\n"+PROGRESS_FILLED+PROGRESS_EMPTY*9+" 10%")
    except: return None
    for pct in [25,40,60,80,100]:
        filled = PROGRESS_FILLED*(pct//10); empty = PROGRESS_EMPTY*(10-(pct//10))
        try:
            await asyncio.sleep(0.45)
            await context.bot.edit_message_text(chat_id=chat_id, message_id=msg.message_id,
                text=f"🔍 Verifying your membership...\n{filled}{empty} {pct}%")
        except: break
    try:
        await context.bot.edit_message_text(chat_id=chat_id, message_id=msg.message_id,
            text="✅ Verification Complete! You are now verified 🎉")
    except: pass
    return msg

# S3 Commands
async def cmd_setverify(update:Update, context:ContextTypes.DEFAULT_TYPE):
    if not await is_admin_or_owner(update): return
    parts = update.message.text.split()
    if len(parts)!=3: return await update.message.reply_text("Usage: /setverify @chan1 @chan2")
    set_verify_channels(update.effective_chat.id, parts[1], parts[2])
    await update.message.reply_text(f"✅ Verify set: {parts[1]} & {parts[2]}")

async def cmd_winnercount(update:Update, context:ContextTypes.DEFAULT_TYPE):
    if not await is_admin_or_owner(update): return
    if not context.args: return await update.message.reply_text("Usage: /winnercount <n>")
    try: n=int(context.args[0])
    except: return await update.message.reply_text("❌ Invalid number.")
    row = gw_get_active(update.effective_chat.id)
    if not row: return await update.message.reply_text("❗ No active giveaway.")
    with db() as c: c.execute("UPDATE giveaways SET winner_count=? WHERE id=?", (n, row[0]))
    await update.message.reply_text(f"✅ Winner count set to {n}.")

async def cmd_autowinner(update:Update, context:ContextTypes.DEFAULT_TYPE):
    if not await is_admin_or_owner(update): return
    if not context.args or context.args[0].lower() not in ("on","off"):
        return await update.message.reply_text("Usage: /autowinner on|off")
    set_autowinner(update.effective_chat.id, 1 if context.args[0].lower()=="on" else 0)
    await update.message.reply_text(f"✅ Auto-winner: {context.args[0].upper()}")

async def cmd_winnerstatus(update:Update, context:ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"ℹ️ Auto-winner is {'ON' if get_autowinner(update.effective_chat.id) else 'OFF'}")

async def cmd_gw(update:Update, context:ContextTypes.DEFAULT_TYPE):
    if not await is_admin_or_owner(update): return
    # /gw "Prize" 10x 9:00 PM
    text = update.message.text
    try:
        a = text.index('"'); b = text.index('"', a+1)
        prize = text[a+1:b]
        rest = text[b+1:].strip().split()
        max_entries = int(re.findall(r"\d+", rest[0])[0])
        tstr = " ".join(rest[1:])
    except:
        return await update.message.reply_text('Usage:\n/gw "Prize" 10x 9:00 PM')

    try:
        H,M = parse_time_str(tstr)
    except:
        return await update.message.reply_text("❌ Bad time.")

    now = datetime.now(TZ)
    end = now.replace(hour=H,minute=M,second=0,microsecond=0)
    if end<=now: end += timedelta(days=1)
    total = int((end-now).total_seconds())

    # initial message body
    bar = make_bar(total,total)
    body = (
        "🎉 MEGA GIVEAWAY ALERT! 🎉\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        f"🎁 Prize: 🎯 {prize}\n"
        f"💥 {max_entries} Premium Accounts!\n"
        f"⏰ Time: Tonight • {end.strftime('%I:%M %p')} (BD Time)\n"
        f"⏳ Remaining: {fmt_dur(total)}\n"
        f"{bar}\n"
        f"👥 Participants: 0\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "🎟 [🎉 Participate Now]\n"
        "3️⃣ Lucky Winners will be selected!\n"
        f"📺 Channel: {CHANNEL_USERNAME}\n"
        f"💬 Group: {GROUP_USERNAME}\n"
        "#Giveaway #PowerPointBreak #LuckyDraw"
        + signature_footer(update.effective_chat.id)
    )
    msg = await update.message.reply_text(body, reply_markup=InlineKeyboardMarkup(
        [[InlineKeyboardButton("🎉 Participate Now", callback_data="GW:join:PENDING")]]
    ))
    # save
    gw_id = gw_insert(update.effective_chat.id, msg.message_id, prize, int(end.timestamp()), max_entries, 3)
    # patch callback data
    try:
        await context.bot.edit_message_reply_markup(
            chat_id=msg.chat_id, message_id=msg.message_id,
            reply_markup=gw_controls_markup(gw_id)
        )
    except: pass
    # start loop
    asyncio.create_task(gw_loop(gw_id))

async def cmd_selectwinner(update:Update, context:ContextTypes.DEFAULT_TYPE):
    if not await is_admin_or_owner(update): return
    row = gw_get_active(update.effective_chat.id)
    if not row: return await update.message.reply_text("❗ No active/awaiting giveaway.")
    gw_id, chat_id, msg_id, prize, end_ts, max_entries, wc, status = row
    winners = pick_winners(gw_id, wc or 3)
    winners_text = " ".join([(f"@{u}" if u else (n or str(i))) for i,u,n in winners]) if winners else "No eligible participants."
    try:
        await application.bot.edit_message_text(
            chat_id=chat_id, message_id=msg_id,
            text=(
                "🎉✨ GIVEAWAY ENDED! ✨🎉\n"
                "━━━━━━━━━━━━━━━━━━━\n"
                f"🎁 Prize: 🎯 {prize}\n"
                f"🏆 Winners: {winners_text}\n\n"
                "🎊 Congratulations to all the Lucky Winners!\n"
                "💫 Thanks for Participating 💖\n"
                "━━━━━━━━━━━━━━━━━━━\n"
                f"📺 Channel: {CHANNEL_USERNAME}\n"
                f"💬 Group: {GROUP_USERNAME}\n"
                "━━━━━━━━━━━━━━━━━━━\n"
                "#Giveaway #PowerPointBreak #Winners #LuckyDraw"
            ) + signature_footer(chat_id)
        )
        with db() as c: c.execute("UPDATE giveaways SET status='done' WHERE id=?", (gw_id,))
        await update.message.reply_text("✅ Winners posted.")
    except: pass

async def cmd_joinedlist(update:Update, context:ContextTypes.DEFAULT_TYPE):
    if not await is_admin_or_owner(update): return
    row = gw_get_active(update.effective_chat.id)
    if not row: return await update.message.reply_text("❗ No active giveaway.")
    parts = list_parts(row[0])
    if not parts: return await update.message.reply_text("📭 No participants yet.")
    lines = ["📋 Real Participants:"]
    for uid,un,nm in parts:
        lines.append(f"- {('@'+un) if un else (nm or str(uid))}")
    await update.message.reply_text("\n".join(lines)[:3900])

async def on_gw_button(update:Update, context:ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if not q.data.startswith("GW:join:"): return
    gw_id = int(q.data.split(":")[2])
    row = gw_get(gw_id)
    if not row or row[7] not in ("running","awaiting"): return
    chat_id, msg_id, prize, end_ts, max_entries, wc, status = row[1], row[2], row[3], row[4], row[5], row[6], row[7]

    # verify membership if configured
    c1,c2 = get_verify_channels(chat_id)
    if c1 and c2:
        ok1=ok2=False
        try:
            m1 = await context.bot.get_chat_member(c1, q.from_user.id); ok1 = m1.status in ("member","administrator","creator")
        except: ok1=False
        try:
            m2 = await context.bot.get_chat_member(c2, q.from_user.id); ok2 = m2.status in ("member","administrator","creator")
        except: ok2=False
        if not (ok1 and ok2):
            try:
                await context.bot.send_message(chat_id=chat_id, reply_to_message_id=msg_id,
                    text=f"❌ Please join both {c1} and {c2} first, then press Participate again.")
            except: pass
            return
        else:
            await inchat_verify_loading(chat_id, msg_id, context)

    username = q.from_user.username or ""
    name = getattr(q.from_user, "full_name", None) or (q.from_user.first_name or "")
    added = add_participant(gw_id, q.from_user.id, username, name)
    if not added:
        try:
            await context.bot.send_message(chat_id=chat_id, reply_to_message_id=msg_id,
                text="🔁 You’ve already participated in this giveaway!\n✨ Sit back and wait for the final results 🏆")
        except: pass
        return
    else:
        try:
            await context.bot.send_message(chat_id=chat_id, reply_to_message_id=msg_id,
                text="✅ You have successfully joined the giveaway!\n🎉 Good luck and stay tuned for the winner announcement!")
        except: pass

    # update main giveaway message
    real = count_part(gw_id); disp = display_count(real)
    left = int(end_ts - int(datetime.now(TZ).timestamp()))
    total = max(1, left)
    bar = make_bar(total, left)
    body = (
        "🎉 MEGA GIVEAWAY ALERT! 🎉\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        f"🎁 Prize: 🎯 {prize}\n"
        f"💥 {max_entries} Premium Accounts!\n"
        f"⏰ Time: Tonight • {datetime.fromtimestamp(end_ts,TZ).strftime('%I:%M %p')} (BD Time)\n"
        f"⏳ Remaining: {fmt_dur(max(0,left))}\n"
        f"{bar}\n"
        f"👥 Participants: {disp}\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "🎟 [🎉 Participate Now]\n"
        "3️⃣ Lucky Winners will be selected!\n"
        f"📺 Channel: {CHANNEL_USERNAME}\n"
        f"💬 Group: {GROUP_USERNAME}\n"
        "#Giveaway #PowerPointBreak #LuckyDraw"
        + signature_footer(chat_id)
    )
    try:
        await context.bot.edit_message_text(chat_id=chat_id, message_id=msg_id, text=body, reply_markup=gw_controls_markup(gw_id))
    except: pass

async def gw_loop(gw_id:int):
    while True:
        row = gw_get(gw_id)
        if not row: break
        chat_id, msg_id, prize, end_ts, max_entries, wc, status = row[1],row[2],row[3],row[4],row[5],row[6],row[7]
        now_ts = int(datetime.now(TZ).timestamp())
        left = end_ts - now_ts

        if left <= 0:
            if get_autowinner(chat_id):
                winners = pick_winners(gw_id, wc or 3)
                winners_text = " ".join([(f"@{u}" if u else (n or str(i))) for i,u,n in winners]) if winners else "No eligible participants."
                try:
                    await application.bot.edit_message_text(
                        chat_id=chat_id, message_id=msg_id,
                        text=(
                            "🎉✨ GIVEAWAY ENDED! ✨🎉\n"
                            "━━━━━━━━━━━━━━━━━━━\n"
                            f"🎁 Prize: 🎯 {prize}\n"
                            f"🏆 Winners: {winners_text}\n\n"
                            "🎊 Congratulations to all the Lucky Winners!\n"
                            "💫 Thanks for Participating 💖\n"
                            "━━━━━━━━━━━━━━━━━━━\n"
                            f"📺 Channel: {CHANNEL_USERNAME}\n"
                            f"💬 Group: {GROUP_USERNAME}\n"
                            "━━━━━━━━━━━━━━━━━━━\n"
                            "#Giveaway #PowerPointBreak #Winners #LuckyDraw"
                        ) + signature_footer(chat_id)
                    )
                    with db() as c: c.execute("UPDATE giveaways SET status='done' WHERE id=?", (gw_id,))
                except: pass
                break
            else:
                try:
                    await application.bot.edit_message_text(
                        chat_id=chat_id, message_id=msg_id,
                        text=(
                            "⏳ Giveaway time ended.\n"
                            "🛑 Awaiting admin to select winners with /selectwinner\n\n"
                            f"🎁 Prize: 🎯 {prize}\n"
                            f"📺 Channel: {CHANNEL_USERNAME}\n"
                            f"💬 Group: {GROUP_USERNAME}"
                        ) + signature_footer(chat_id),
                        reply_markup=gw_controls_markup(gw_id)
                    )
                    with db() as c: c.execute("UPDATE giveaways SET status='awaiting' WHERE id=?", (gw_id,))
                except: pass
                break

        # live refresh
        real = count_part(gw_id); disp = display_count(real)
        total = max(1, left)
        bar = make_bar(total, left)
        body = (
            "🎉 MEGA GIVEAWAY ALERT! 🎉\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            f"🎁 Prize: 🎯 {prize}\n"
            f"💥 {max_entries} Premium Accounts!\n"
            f"⏰ Time: Tonight • {datetime.fromtimestamp(end_ts,TZ).strftime('%I:%M %p')} (BD Time)\n"
            f"⏳ Remaining: {fmt_dur(left)}\n"
            f"{bar}\n"
            f"👥 Participants: {disp}\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "🎟 [🎉 Participate Now]\n"
            f"📺 Channel: {CHANNEL_USERNAME}\n"
            f"💬 Group: {GROUP_USERNAME}\n"
            "#Giveaway #PowerPointBreak #LuckyDraw"
            + signature_footer(chat_id)
        )
        try:
            await application.bot.edit_message_text(chat_id=chat_id, message_id=msg_id, text=body, reply_markup=gw_controls_markup(gw_id))
        except: pass
        await asyncio.sleep(1)

# -------------------- APP BUILD --------------------
application = ApplicationBuilder().token(BOT_TOKEN).build()

# General
application.add_handler(CommandHandler("start", cmd_start))
application.add_handler(CommandHandler("allcd", cmd_allcd))

# Owner / Signature
application.add_handler(CommandHandler("setsignature", cmd_setsignature))
application.add_handler(CommandHandler("viewsignature", cmd_viewsignature))
application.add_handler(CommandHandler("setowner", cmd_setowner))
application.add_handler(CommandHandler("ownerinfo", cmd_ownerinfo))

# System-1
application.add_handler(CommandHandler("livepost", cmd_livepost))
application.add_handler(CommandHandler("changetime", cmd_changetime))
application.add_handler(CommandHandler("extendtime", cmd_extendtime))

# System-2
application.add_handler(CommandHandler("schedulepost", cmd_schedulepost))

# System-3
application.add_handler(CommandHandler("setverify", cmd_setverify))
application.add_handler(CommandHandler("gw", cmd_gw))
application.add_handler(CommandHandler("winnercount", cmd_winnercount))
application.add_handler(CommandHandler("autowinner", cmd_autowinner))
application.add_handler(CommandHandler("winnerstatus", cmd_winnerstatus))
application.add_handler(CommandHandler("selectwinner", cmd_selectwinner))
application.add_handler(CommandHandler("joinedlist", cmd_joinedlist))
application.add_handler(CallbackQueryHandler(on_gw_button, pattern=r"^GW:join:\d+$"))

# Background scheduler loop
asyncio.get_event_loop().create_task(scheduler_loop(application))

print("✅ PowerPointBreak Bot v19 Loaded Successfully.")
application.run_polling(allowed_updates=["message","edited_message","callback_query"])
