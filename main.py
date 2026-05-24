import asyncio
import sqlite3
import json
import hashlib
import hmac
import aiohttp
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# ==================== КОНФИГ ====================

BOT_TOKEN = "8305173759:AAGUQBAxSuBLgcxquzUliGTkwoBQpHtepG8"
TON_WALLET = "UQDtRwosWY6VfPnwovLRcF2yo46Xv3BcK-mV1Da-1LwbVIaE"
USDT_WALLET = "TKPuYeveSA2giJV9fFcgbCDsY6abmzMS7Z"
SUPPORT_USERNAME = "@MollyWhip1"
ADMIN_IDS = [8353710361]
LOG_CHAT_ID = 8353710361

WORKERS = {
    1: {"name_ru": "🧑‍🌾 Стажёр", "name_en": "🧑‍🌾 Intern", "cost": 1, "income": 0.003},
    2: {"name_ru": "👨‍🔧 Разнорабочий", "name_en": "👨‍🔧 Laborer", "cost": 5, "income": 0.02},
    3: {"name_ru": "👷 Шахтёр", "name_en": "👷 Miner", "cost": 20, "income": 0.10},
    4: {"name_ru": "🔧 Инженер", "name_en": "🔧 Engineer", "cost": 50, "income": 0.30},
    5: {"name_ru": "🧙‍♂️ Бурильщик", "name_en": "🧙‍♂️ Driller", "cost": 100, "income": 0.70},
    6: {"name_ru": "⚙️ Механик", "name_en": "⚙️ Mechanic", "cost": 200, "income": 1.60},
    7: {"name_ru": "🏭 Директор шахты", "name_en": "🏭 Mine Director", "cost": 500, "income": 4.50},
    8: {"name_ru": "👑 Магнат", "name_en": "👑 Magnate", "cost": 1000, "income": 10.00},
    9: {"name_ru": "⭐ Олигарх", "name_en": "⭐ Oligarch", "cost": 2500, "income": 30.00},
    10: {"name_ru": "💎 Крипто-король", "name_en": "💎 Crypto King", "cost": 5000, "income": 75.00},
}

FARM_LEVELS = {
    1: {"workers": 0, "bonus": 0, "cost": 0},
    2: {"workers": 5, "bonus": 5, "cost": 50},
    3: {"workers": 10, "bonus": 10, "cost": 100},
    4: {"workers": 20, "bonus": 15, "cost": 200},
    5: {"workers": 35, "bonus": 20, "cost": 400},
    6: {"workers": 50, "bonus": 30, "cost": 700},
    7: {"workers": 75, "bonus": 40, "cost": 1000},
    8: {"workers": 100, "bonus": 50, "cost": 1500},
    9: {"workers": 150, "bonus": 60, "cost": 2000},
    10: {"workers": 200, "bonus": 75, "cost": 3000},
}

DAILY_BONUSES = {
    1: 0.05, 2: 0.07, 3: 0.10, 4: 0.15, 5: 0.20,
    6: 0.30, 7: 0.50, 14: 1.00, 21: 2.00, 30: 5.00,
}

REFERRAL_BONUS = 0.5
REFERRAL_PERCENT = 0.07

WITHDRAW_MIN = 10
WITHDRAW_FEE = 0.05

# ==================== БАЗА ДАННЫХ ====================

DB_PATH = "bot.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            balance REAL DEFAULT 0,
            total_workers INTEGER DEFAULT 0,
            farm_level INTEGER DEFAULT 1,
            last_collect TEXT,
            streak INTEGER DEFAULT 0,
            last_daily TEXT,
            referred_by INTEGER,
            language TEXT DEFAULT 'ru',
            created_at TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS workers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            worker_type INTEGER,
            bought_at TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS withdrawals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount REAL,
            address TEXT,
            status TEXT DEFAULT 'pending',
            created_at TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS deposits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount REAL,
            tx_hash TEXT UNIQUE,
            status TEXT DEFAULT 'pending',
            comment TEXT,
            created_at TEXT,
            processed_at TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS deposit_sessions (
            user_id INTEGER PRIMARY KEY,
            amount REAL,
            comment TEXT,
            expires_at TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS processed_tx (
            tx_hash TEXT PRIMARY KEY,
            processed_at TEXT
        )
    ''')
    
    conn.commit()
    conn.close()

def get_user(user_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {
            "user_id": row[0],
            "username": row[1],
            "balance": row[2],
            "total_workers": row[3],
            "farm_level": row[4],
            "last_collect": row[5],
            "streak": row[6],
            "last_daily": row[7],
            "referred_by": row[8],
            "language": row[9] if len(row) > 9 else "ru",
            "created_at": row[10] if len(row) > 10 else None
        }
    return None

def create_user(user_id, username, referred_by=None):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR IGNORE INTO users (user_id, username, last_collect, referred_by, created_at)
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, username, datetime.now().isoformat(), referred_by, datetime.now().isoformat()))
    
    if referred_by:
        cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (REFERRAL_BONUS, referred_by))
    
    conn.commit()
    conn.close()

def update_user_language(user_id, language):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET language = ? WHERE user_id = ?", (language, user_id))
    conn.commit()
    conn.close()

def update_balance(user_id, amount):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()

def get_workers(user_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT worker_type, COUNT(*) FROM workers WHERE user_id = ? GROUP BY worker_type", (user_id,))
    workers = cursor.fetchall()
    conn.close()
    return workers

def add_worker(user_id, worker_type):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO workers (user_id, worker_type, bought_at) VALUES (?, ?, ?)",
                   (user_id, worker_type, datetime.now().isoformat()))
    cursor.execute("UPDATE users SET total_workers = total_workers + 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def get_worker_count(user_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM workers WHERE user_id = ?", (user_id,))
    count = cursor.fetchone()[0]
    conn.close()
    return count

def update_farm_level(user_id, level):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET farm_level = ? WHERE user_id = ?", (level, user_id))
    conn.commit()
    conn.close()

def update_last_collect(user_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET last_collect = ? WHERE user_id = ?", (datetime.now().isoformat(), user_id))
    conn.commit()
    conn.close()

def update_daily_streak(user_id, streak, last_daily):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET streak = ?, last_daily = ? WHERE user_id = ?", (streak, last_daily, user_id))
    conn.commit()
    conn.close()

def get_daily_bonus(streak):
    bonus = DAILY_BONUSES.get(1, 0.05)
    for day, amount in sorted(DAILY_BONUSES.items()):
        if streak >= day:
            bonus = amount
    return bonus

def create_withdrawal(user_id, amount, address):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO withdrawals (user_id, amount, address, created_at)
        VALUES (?, ?, ?, ?)
    ''', (user_id, amount, address, datetime.now().isoformat()))
    withdraw_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return withdraw_id

def get_pending_withdrawals():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM withdrawals WHERE status = 'pending'")
    withdrawals = cursor.fetchall()
    conn.close()
    return withdrawals

def update_withdrawal_status(withdraw_id, status):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE withdrawals SET status = ? WHERE id = ?", (status, withdraw_id))
    conn.commit()
    conn.close()

def get_top_players(limit=10):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT username, balance FROM users ORDER BY balance DESC LIMIT ?", (limit,))
    top = cursor.fetchall()
    conn.close()
    return top

def get_referrals_count(user_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users WHERE referred_by = ?", (user_id,))
    count = cursor.fetchone()[0]
    conn.close()
    return count

def create_deposit_session(user_id, amount):
    import uuid
    comment = f"DEPOSIT_{user_id}_{uuid.uuid4().hex[:8]}"
    expires_at = (datetime.now() + timedelta(hours=1)).isoformat()
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO deposit_sessions (user_id, amount, comment, expires_at)
        VALUES (?, ?, ?, ?)
    ''', (user_id, amount, comment, expires_at))
    conn.commit()
    conn.close()
    return comment

def get_deposit_session(user_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM deposit_sessions WHERE user_id = ? AND expires_at > ?", 
                   (user_id, datetime.now().isoformat()))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {"user_id": row[0], "amount": row[1], "comment": row[2], "expires_at": row[3]}
    return None

def clear_deposit_session(user_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM deposit_sessions WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def add_deposit(user_id, amount, tx_hash, comment):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO deposits (user_id, amount, tx_hash, comment, status, created_at, processed_at)
        VALUES (?, ?, ?, ?, 'completed', ?, ?)
    ''', (user_id, amount, tx_hash, comment, datetime.now().isoformat(), datetime.now().isoformat()))
    conn.commit()
    conn.close()

def is_tx_processed(tx_hash):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM processed_tx WHERE tx_hash = ?", (tx_hash,))
    exists = cursor.fetchone() is not None
    conn.close()
    return exists

def mark_tx_processed(tx_hash):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO processed_tx (tx_hash, processed_at) VALUES (?, ?)",
                   (tx_hash, datetime.now().isoformat()))
    conn.commit()
    conn.close()

# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================

def format_ton(amount):
    return f"{amount:.3f}"

def calculate_income(user_id):
    user = get_user(user_id)
    if not user:
        return 0
    
    workers = get_workers(user_id)
    income = 0
    for w in workers:
        worker_type = w[0]
        count = w[1]
        income += WORKERS[worker_type]["income"] * count
    
    farm_level = user["farm_level"]
    bonus = FARM_LEVELS[farm_level]["bonus"] / 100
    income = income * (1 + bonus)
    
    return round(income, 4)

def calculate_pending(user_id):
    user = get_user(user_id)
    if not user or not user["last_collect"]:
        return 0
    
    try:
        last_collect = datetime.fromisoformat(user["last_collect"])
    except:
        return 0
    
    income_day = calculate_income(user_id)
    hours_passed = (datetime.now() - last_collect).total_seconds() / 3600
    pending = income_day * (hours_passed / 24)
    
    return round(pending, 4)

def get_streak_bar(streak):
    filled = min(streak, 7)
    return "🟩" * filled + "⬜" * (7 - filled)

# ==================== ПРОВЕРКА ПЛАТЕЖЕЙ ====================

async def check_ton_transactions():
    """Проверка транзакций TON через API"""
    async with aiohttp.ClientSession() as session:
        url = f"https://toncenter.com/api/v2/getTransactions"
        params = {
            "address": TON_WALLET,
            "limit": 50
        }
        
        try:
            async with session.get(url, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    for tx in data.get("result", []):
                        tx_hash = tx.get("transaction_id", {}).get("hash")
                        if not tx_hash or is_tx_processed(tx_hash):
                            continue
                        
                        comment = ""
                        for msg in tx.get("in_msg", {}).get("message", ""):
                            comment = msg
                            break
                        
                        if not comment or not comment.startswith("DEPOSIT_"):
                            continue
                        
                        parts = comment.split("_")
                        if len(parts) >= 2:
                            try:
                                user_id = int(parts[1])
                                amount = float(tx.get("amount", 0)) / 1_000_000_000
                                
                                if amount > 0:
                                    update_balance(user_id, amount)
                                    add_deposit(user_id, amount, tx_hash, comment)
                                    mark_tx_processed(tx_hash)
                                    clear_deposit_session(user_id)
                                    
                                    bot = Bot(token=BOT_TOKEN)
                                    lang = get_user(user_id)["language"] if get_user(user_id) else "ru"
                                    text_ru = f"✅ <b>Пополнение успешно!</b>\n\n💰 Зачислено: <b>{format_ton(amount)} TON</b>\n💳 Новый баланс: <b>{format_ton(get_user(user_id)['balance'])} TON</b>"
                                    text_en = f"✅ <b>Deposit successful!</b>\n\n💰 Credited: <b>{format_ton(amount)} TON</b>\n💳 New balance: <b>{format_ton(get_user(user_id)['balance'])} TON</b>"
                                    await bot.send_message(user_id, text_ru if lang == "ru" else text_en, parse_mode="HTML")
                                    await bot.close()
                            except (ValueError, IndexError):
                                pass
        except Exception as e:
            print(f"Ошибка проверки TON: {e}")

async def start_payment_checker():
    while True:
        try:
            await check_ton_transactions()
        except Exception as e:
            print(f"Payment checker error: {e}")
        await asyncio.sleep(30)

# ==================== КЛАВИАТУРЫ ====================

def get_main_keyboard(lang="ru"):
    if lang == "ru":
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👤 ПРОФИЛЬ", callback_data="menu_profile")],
            [InlineKeyboardButton(text="🏪 МАГАЗИН", callback_data="menu_shop")],
            [InlineKeyboardButton(text="👷 МОИ РАБОЧИЕ", callback_data="menu_workers")],
            [InlineKeyboardButton(text="🌾 ФЕРМА", callback_data="menu_farm")],
            [InlineKeyboardButton(text="🎁 БОНУС", callback_data="menu_daily")],
            [InlineKeyboardButton(text="👥 РЕФЕРАЛЫ", callback_data="menu_referral")],
            [InlineKeyboardButton(text="🏆 ТОП", callback_data="menu_top")],
            [InlineKeyboardButton(text="🌍 ЯЗЫК", callback_data="menu_language")],
        ])
    else:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👤 PROFILE", callback_data="menu_profile")],
            [InlineKeyboardButton(text="🏪 SHOP", callback_data="menu_shop")],
            [InlineKeyboardButton(text="👷 MY WORKERS", callback_data="menu_workers")],
            [InlineKeyboardButton(text="🌾 FARM", callback_data="menu_farm")],
            [InlineKeyboardButton(text="🎁 BONUS", callback_data="menu_daily")],
            [InlineKeyboardButton(text="👥 REFERRALS", callback_data="menu_referral")],
            [InlineKeyboardButton(text="🏆 TOP", callback_data="menu_top")],
            [InlineKeyboardButton(text="🌍 LANGUAGE", callback_data="menu_language")],
        ])

def get_back_keyboard(lang="ru"):
    text = "◀️ НАЗАД" if lang == "ru" else "◀️ BACK"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=text, callback_data="back_to_menu")]
    ])

def get_shop_keyboard(lang="ru"):
    buttons = []
    for wid, w in WORKERS.items():
        name = w[f"name_{lang}"] if lang in w else w["name_ru"]
        buttons.append([InlineKeyboardButton(
            text=f"🔹 {name} — {w['cost']} TON",
            callback_data=f"buy_{wid}"
        )])
    buttons.append([InlineKeyboardButton(text="◀️ НАЗАД" if lang == "ru" else "◀️ BACK", callback_data="back_to_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_workers_keyboard(lang="ru"):
    text = "💰 СОБРАТЬ" if lang == "ru" else "💰 COLLECT"
    back = "◀️ НАЗАД" if lang == "ru" else "◀️ BACK"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=text, callback_data="collect")],
        [InlineKeyboardButton(text=back, callback_data="back_to_menu")],
    ])

def get_farm_keyboard(user, lang="ru"):
    buttons = []
    current_level = user["farm_level"]
    if current_level < 10:
        next_level = FARM_LEVELS[current_level + 1]
        if user["total_workers"] >= next_level["workers"] and user["balance"] >= next_level["cost"]:
            text = f"⬆️ УЛУЧШИТЬ ({next_level['cost']} TON)" if lang == "ru" else f"⬆️ UPGRADE ({next_level['cost']} TON)"
            buttons.append([InlineKeyboardButton(text=text, callback_data="upgrade_farm")])
    back = "◀️ НАЗАД" if lang == "ru" else "◀️ BACK"
    buttons.append([InlineKeyboardButton(text=back, callback_data="back_to_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_profile_keyboard(lang="ru"):
    deposit = "💎 ПОПОЛНИТЬ" if lang == "ru" else "💎 DEPOSIT"
    withdraw = "💸 ВЫВЕСТИ" if lang == "ru" else "💸 WITHDRAW"
    back = "◀️ НАЗАД" if lang == "ru" else "◀️ BACK"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=deposit, callback_data="menu_deposit")],
        [InlineKeyboardButton(text=withdraw, callback_data="menu_withdraw")],
        [InlineKeyboardButton(text=back, callback_data="back_to_menu")],
    ])

def get_deposit_keyboard(lang="ru"):
    back = "◀️ НАЗАД" if lang == "ru" else "◀️ BACK"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 10 TON", callback_data="deposit_10")],
        [InlineKeyboardButton(text="💎 25 TON", callback_data="deposit_25")],
        [InlineKeyboardButton(text="💎 50 TON", callback_data="deposit_50")],
        [InlineKeyboardButton(text="💎 100 TON", callback_data="deposit_100")],
        [InlineKeyboardButton(text="💎 250 TON", callback_data="deposit_250")],
        [InlineKeyboardButton(text="💎 500 TON", callback_data="deposit_500")],
        [InlineKeyboardButton(text="💎 1000 TON", callback_data="deposit_1000")],
        [InlineKeyboardButton(text=back, callback_data="back_to_menu")],
    ])

def get_withdraw_keyboard(lang="ru"):
    withdraw = "💸 ВЫВЕСТИ" if lang == "ru" else "💸 WITHDRAW"
    back = "◀️ НАЗАД" if lang == "ru" else "◀️ BACK"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=withdraw, callback_data="withdraw_start")],
        [InlineKeyboardButton(text=back, callback_data="back_to_menu")],
    ])

def get_language_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇷🇺 РУССКИЙ", callback_data="lang_ru")],
        [InlineKeyboardButton(text="🇬🇧 ENGLISH", callback_data="lang_en")],
        [InlineKeyboardButton(text="◀️ НАЗАД", callback_data="back_to_menu")],
    ])

def get_admin_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 НАЧИСЛИТЬ", callback_data="admin_add")],
        [InlineKeyboardButton(text="✅ ЗАЯВКИ", callback_data="admin_withdrawals")],
        [InlineKeyboardButton(text="📊 СТАТИСТИКА", callback_data="admin_stats")],
    ])

def get_withdrawal_buttons(withdraw_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ ОДОБРИТЬ", callback_data=f"approve_{withdraw_id}"),
            InlineKeyboardButton(text="❌ ОТКЛОНИТЬ", callback_data=f"reject_{withdraw_id}"),
        ]
    ])

# ==================== FSM СОСТОЯНИЯ ====================

class WithdrawStates(StatesGroup):
    waiting_amount = State()
    waiting_address = State()

class AdminStates(StatesGroup):
    waiting_user_id = State()
    waiting_amount = State()

# ==================== БОТ ====================

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# -------------------- СТАРТ --------------------

@dp.message(CommandStart())
async def cmd_start(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username or ""
    
    user = get_user(user_id)
    
    args = message.text.split()
    ref_id = None
    if len(args) > 1:
        try:
            ref_id = int(args[1])
            if ref_id == user_id:
                ref_id = None
        except:
            pass
    
    is_new = user is None
    
    if is_new:
        create_user(user_id, username, ref_id)
        user = get_user(user_id)
        
        if ref_id:
            ref_user = get_user(ref_id)
            if ref_user:
                await bot.send_message(
                    ref_id,
                    f"🎉 <b>Новый реферал!</b>\n\n"
                    f"👤 Пользователь @{username} присоединился по вашей ссылке!\n"
                    f"💰 +{REFERRAL_BONUS} TON начислено на баланс!",
                    parse_mode="HTML"
                )
                await bot.send_message(
                    LOG_CHAT_ID,
                    f"👤 <b>Новый пользователь</b>\n"
                    f"├ 🆔 ID: <code>{user_id}</code>\n"
                    f"├ 👤 Username: @{username}\n"
                    f"└ 👥 Приглашён: @{ref_user['username']} (ID: {ref_id})",
                    parse_mode="HTML"
                )
    
    lang = user["language"] if user else "ru"
    
    # Приветствие
    if is_new:
        if lang == "ru":
            await message.answer(
                f"🌟 <b>ДОБРО ПОЖАЛОВАТЬ В WORKERS ON TON!</b> 🌟\n\n"
                f"👋 Привет, {username}!\n\n"
                f"💰 Зарабатывай TON, покупай рабочих и прокачивай ферму!\n"
                f"👥 Приглашай друзей и получай бонусы!\n\n"
                f"👇 <b>Начни своё путешествие прямо сейчас!</b>",
                parse_mode="HTML"
            )
        else:
            await message.answer(
                f"🌟 <b>WELCOME TO WORKERS ON TON!</b> 🌟\n\n"
                f"👋 Hi, {username}!\n\n"
                f"💰 Earn TON, buy workers and upgrade your farm!\n"
                f"👥 Invite friends and get bonuses!\n\n"
                f"👇 <b>Start your journey right now!</b>",
                parse_mode="HTML"
            )
    
    await show_main_menu(message, lang)

async def show_main_menu(message: Message, lang="ru"):
    user_id = message.from_user.id
    user = get_user(user_id)
    income = calculate_income(user_id)
    pending = calculate_pending(user_id)
    bar = get_streak_bar(user["streak"])
    
    if lang == "ru":
        text = (
            f"╔══════════════════════════════════╗\n"
            f"║      🏭 <b>WORKERS ON TON</b>       ║\n"
            f"╚══════════════════════════════════╝\n\n"
            f"👤 <b>Пользователь:</b> {user['username'] or 'Аноним'}\n\n"
            f"┌─────────────────────────────────┐\n"
            f"│ 💰 <b>Баланс:</b> {format_ton(user['balance'])} TON\n"
            f"│ 📈 <b>Доход/день:</b> {format_ton(income)} TON\n"
            f"│ 👷 <b>Рабочих:</b> {user['total_workers']}\n"
            f"│ 🌾 <b>Уровень фермы:</b> {user['farm_level']}/10\n"
            f"└─────────────────────────────────┘\n\n"
            f"⏳ <b>Накоплено:</b> {format_ton(pending)} TON\n"
            f"{bar}\n\n"
            f"🔥 <b>Серия входов:</b> {user['streak']} дней\n\n"
            f"👇 <b>Выберите действие:</b>"
        )
    else:
        text = (
            f"╔══════════════════════════════════╗\n"
            f"║      🏭 <b>WORKERS ON TON</b>       ║\n"
            f"╚══════════════════════════════════╝\n\n"
            f"👤 <b>User:</b> {user['username'] or 'Anonymous'}\n\n"
            f"┌─────────────────────────────────┐\n"
            f"│ 💰 <b>Balance:</b> {format_ton(user['balance'])} TON\n"
            f"│ 📈 <b>Income/day:</b> {format_ton(income)} TON\n"
            f"│ 👷 <b>Workers:</b> {user['total_workers']}\n"
            f"│ 🌾 <b>Farm level:</b> {user['farm_level']}/10\n"
            f"└─────────────────────────────────┘\n\n"
            f"⏳ <b>Pending:</b> {format_ton(pending)} TON\n"
            f"{bar}\n\n"
            f"🔥 <b>Login streak:</b> {user['streak']} days\n\n"
            f"👇 <b>Choose action:</b>"
        )
    
    await message.answer(text, reply_markup=get_main_keyboard(lang), parse_mode="HTML")

@dp.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    lang = user["language"] if user else "ru"
    income = calculate_income(callback.from_user.id)
    pending = calculate_pending(callback.from_user.id)
    bar = get_streak_bar(user["streak"])
    
    if lang == "ru":
        text = (
            f"╔══════════════════════════════════╗\n"
            f"║      🏭 <b>WORKERS ON TON</b>       ║\n"
            f"╚══════════════════════════════════╝\n\n"
            f"👤 <b>Пользователь:</b> {user['username'] or 'Аноним'}\n\n"
            f"┌─────────────────────────────────┐\n"
            f"│ 💰 <b>Баланс:</b> {format_ton(user['balance'])} TON\n"
            f"│ 📈 <b>Доход/день:</b> {format_ton(income)} TON\n"
            f"│ 👷 <b>Рабочих:</b> {user['total_workers']}\n"
            f"│ 🌾 <b>Уровень фермы:</b> {user['farm_level']}/10\n"
            f"└─────────────────────────────────┘\n\n"
            f"⏳ <b>Накоплено:</b> {format_ton(pending)} TON\n"
            f"{bar}\n\n"
            f"🔥 <b>Серия входов:</b> {user['streak']} дней\n\n"
            f"👇 <b>Выберите действие:</b>"
        )
    else:
        text = (
            f"╔══════════════════════════════════╗\n"
            f"║      🏭 <b>WORKERS ON TON</b>       ║\n"
            f"╚══════════════════════════════════╝\n\n"
            f"👤 <b>User:</b> {user['username'] or 'Anonymous'}\n\n"
            f"┌─────────────────────────────────┐\n"
            f"│ 💰 <b>Balance:</b> {format_ton(user['balance'])} TON\n"
            f"│ 📈 <b>Income/day:</b> {format_ton(income)} TON\n"
            f"│ 👷 <b>Workers:</b> {user['total_workers']}\n"
            f"│ 🌾 <b>Farm level:</b> {user['farm_level']}/10\n"
            f"└─────────────────────────────────┘\n\n"
            f"⏳ <b>Pending:</b> {format_ton(pending)} TON\n"
            f"{bar}\n\n"
            f"🔥 <b>Login streak:</b> {user['streak']} days\n\n"
            f"👇 <b>Choose action:</b>"
        )
    
    await callback.message.edit_text(text, reply_markup=get_main_keyboard(lang), parse_mode="HTML")
    await callback.answer()

# -------------------- ПРОФИЛЬ --------------------

@dp.callback_query(F.data == "menu_profile")
async def menu_profile(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    lang = user["language"] if user else "ru"
    
    if lang == "ru":
        text = (
            f"╔══════════════════════════════════╗\n"
            f"║         👤 <b>ПРОФИЛЬ</b>           ║\n"
            f"╚══════════════════════════════════╝\n\n"
            f"🆔 <b>ID:</b> <code>{callback.from_user.id}</code>\n"
            f"👤 <b>Имя:</b> {user['username'] or 'Не указано'}\n\n"
            f"┌─────────────────────────────────┐\n"
            f"│ 💰 <b>Баланс:</b> {format_ton(user['balance'])} TON\n"
            f"│ 👷 <b>Рабочих:</b> {user['total_workers']}\n"
            f"│ 🌾 <b>Уровень фермы:</b> {user['farm_level']}/10\n"
            f"│ 📈 <b>Доход/день:</b> {format_ton(calculate_income(callback.from_user.id))} TON\n"
            f"└─────────────────────────────────┘"
        )
    else:
        text = (
            f"╔══════════════════════════════════╗\n"
            f"║         👤 <b>PROFILE</b>           ║\n"
            f"╚══════════════════════════════════╝\n\n"
            f"🆔 <b>ID:</b> <code>{callback.from_user.id}</code>\n"
            f"👤 <b>Name:</b> {user['username'] or 'Not specified'}\n\n"
            f"┌─────────────────────────────────┐\n"
            f"│ 💰 <b>Balance:</b> {format_ton(user['balance'])} TON\n"
            f"│ 👷 <b>Workers:</b> {user['total_workers']}\n"
            f"│ 🌾 <b>Farm level:</b> {user['farm_level']}/10\n"
            f"│ 📈 <b>Income/day:</b> {format_ton(calculate_income(callback.from_user.id))} TON\n"
            f"└─────────────────────────────────┘"
        )
    
    await callback.message.edit_text(text, reply_markup=get_profile_keyboard(lang), parse_mode="HTML")
    await callback.answer()

# -------------------- ПОПОЛНЕНИЕ --------------------

@dp.callback_query(F.data == "menu_deposit")
async def menu_deposit(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    lang = user["language"] if user else "ru"
    
    if lang == "ru":
        text = (
            f"╔══════════════════════════════════╗\n"
            f"║        💎 <b>ПОПОЛНЕНИЕ</b>         ║\n"
            f"╚══════════════════════════════════╝\n\n"
            f"💰 <b>Ваш баланс:</b> {format_ton(user['balance'])} TON\n\n"
            f"👇 <b>Выберите сумму:</b>"
        )
    else:
        text = (
            f"╔══════════════════════════════════╗\n"
            f"║        💎 <b>DEPOSIT</b>            ║\n"
            f"╚══════════════════════════════════╝\n\n"
            f"💰 <b>Your balance:</b> {format_ton(user['balance'])} TON\n\n"
            f"👇 <b>Choose amount:</b>"
        )
    
    await callback.message.edit_text(text, reply_markup=get_deposit_keyboard(lang), parse_mode="HTML")
    await callback.answer()

@dp.callback_query(F.data.startswith("deposit_"))
async def deposit_amount(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    lang = user["language"] if user else "ru"
    amount = int(callback.data.split("_")[1])
    
    comment = create_deposit_session(callback.from_user.id, amount)
    
    if lang == "ru":
        text = (
            f"╔══════════════════════════════════╗\n"
            f"║        💎 <b>ОПЛАТА</b>             ║\n"
            f"╚══════════════════════════════════╝\n\n"
            f"💰 <b>Сумма:</b> {amount} TON\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📤 <b>Отправьте перевод на кошелёк:</b>\n\n"
            f"💎 <b>TON:</b>\n<code>{TON_WALLET}</code>\n\n"
            f"💵 <b>USDT (TRC20):</b>\n<code>{USDT_WALLET}</code>\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📝 <b>ВАЖНО!</b>\n"
            f"В комментарии к платежу укажите:\n"
            f"<code>{comment}</code>\n\n"
            f"❗ Без этого комментария средства не зачислятся!\n"
            f"💰 Пополнение происходит автоматически в течение 1-5 минут.\n\n"
            f"📩 <b>Поддержка:</b> {SUPPORT_USERNAME}"
        )
    else:
        text = (
            f"╔══════════════════════════════════╗\n"
            f"║        💎 <b>PAYMENT</b>            ║\n"
            f"╚══════════════════════════════════╝\n\n"
            f"💰 <b>Amount:</b> {amount} TON\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📤 <b>Send payment to wallet:</b>\n\n"
            f"💎 <b>TON:</b>\n<code>{TON_WALLET}</code>\n\n"
            f"💵 <b>USDT (TRC20):</b>\n<code>{USDT_WALLET}</code>\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📝 <b>IMPORTANT!</b>\n"
            f"In the payment comment specify:\n"
            f"<code>{comment}</code>\n\n"
            f"❗ Without this comment, funds will not be credited!\n"
            f"💰 Deposit is credited automatically within 1-5 minutes.\n\n"
            f"📩 <b>Support:</b> {SUPPORT_USERNAME}"
        )
    
    await callback.message.edit_text(text, reply_markup=get_back_keyboard(lang), parse_mode="HTML")
    await callback.answer()

# -------------------- ВЫВОД --------------------

@dp.callback_query(F.data == "menu_withdraw")
async def menu_withdraw(callback: CallbackQuery, state: FSMContext):
    user = get_user(callback.from_user.id)
    lang = user["language"] if user else "ru"
    
    if lang == "ru":
        text = (
            f"╔══════════════════════════════════╗\n"
            f"║        💸 <b>ВЫВОД СРЕДСТВ</b>       ║\n"
            f"╚══════════════════════════════════╝\n\n"
            f"💰 <b>Доступно:</b> {format_ton(user['balance'])} TON\n"
            f"📋 <b>Минимум:</b> {WITHDRAW_MIN} TON\n"
            f"💸 <b>Комиссия:</b> {int(WITHDRAW_FEE * 100)}%\n\n"
            f"✏️ <b>Введите сумму вывода:</b>"
        )
    else:
        text = (
            f"╔══════════════════════════════════╗\n"
            f"║        💸 <b>WITHDRAW</b>           ║\n"
            f"╚══════════════════════════════════╝\n\n"
            f"💰 <b>Available:</b> {format_ton(user['balance'])} TON\n"
            f"📋 <b>Minimum:</b> {WITHDRAW_MIN} TON\n"
            f"💸 <b>Fee:</b> {int(WITHDRAW_FEE * 100)}%\n\n"
            f"✏️ <b>Enter withdrawal amount:</b>"
        )
    
    await callback.message.edit_text(text, reply_markup=get_back_keyboard(lang), parse_mode="HTML")
    await state.set_state(WithdrawStates.waiting_amount)
    await callback.answer()

@dp.message(WithdrawStates.waiting_amount)
async def withdraw_amount(message: Message, state: FSMContext):
    user = get_user(message.from_user.id)
    lang = user["language"] if user else "ru"
    
    try:
        amount = float(message.text.strip())
    except:
        await message.answer("❌ " + ("Введите корректное число!" if lang == "ru" else "Enter a valid number!"))
        return
    
    if amount < WITHDRAW_MIN:
        await message.answer(f"❌ " + ("Минимальная сумма" if lang == "ru" else "Minimum amount") + f": {WITHDRAW_MIN} TON")
        return
    
    if amount > user["balance"]:
        await message.answer(f"❌ " + ("Недостаточно средств!" if lang == "ru" else "Insufficient funds!") + f" {format_ton(user['balance'])} TON")
        return
    
    fee = amount * WITHDRAW_FEE
    final_amount = amount - fee
    
    await state.update_data(amount=amount, fee=fee, final_amount=final_amount)
    await state.set_state(WithdrawStates.waiting_address)
    
    if lang == "ru":
        await message.answer(
            f"💰 <b>Сумма:</b> {format_ton(amount)} TON\n"
            f"💸 <b>Комиссия ({int(WITHDRAW_FEE*100)}%):</b> {format_ton(fee)} TON\n"
            f"📤 <b>К выплате:</b> {format_ton(final_amount)} TON\n\n"
            f"📝 <b>Введите адрес TON кошелька:</b>",
            parse_mode="HTML"
        )
    else:
        await message.answer(
            f"💰 <b>Amount:</b> {format_ton(amount)} TON\n"
            f"💸 <b>Fee ({int(WITHDRAW_FEE*100)}%):</b> {format_ton(fee)} TON\n"
            f"📤 <b>To receive:</b> {format_ton(final_amount)} TON\n\n"
            f"📝 <b>Enter TON wallet address:</b>",
            parse_mode="HTML"
        )

@dp.message(WithdrawStates.waiting_address)
async def withdraw_address(message: Message, state: FSMContext):
    user = get_user(message.from_user.id)
    lang = user["language"] if user else "ru"
    address = message.text.strip()
    data = await state.get_data()
    
    withdraw_id = create_withdrawal(message.from_user.id, data["amount"], address)
    update_balance(message.from_user.id, -data["amount"])
    
    for admin_id in ADMIN_IDS:
        try:
            admin_text = f"💸 <b>НОВАЯ ЗАЯВКА НА ВЫВОД</b>\n\n👤 ID: {message.from_user.id}\n💰 Сумма: {data['amount']} TON\n📤 К выплате: {data['final_amount']} TON\n📍 Адрес: {address}"
            await bot.send_message(admin_id, admin_text, reply_markup=get_withdrawal_buttons(withdraw_id), parse_mode="HTML")
        except:
            pass
    
    if lang == "ru":
        await message.answer(
            f"✅ <b>Заявка отправлена!</b>\n\n"
            f"💰 Сумма: {format_ton(data['amount'])} TON\n"
            f"📤 К выплате: {format_ton(data['final_amount'])} TON\n\n"
            f"⏰ Ожидайте подтверждения администратора.",
            reply_markup=get_back_keyboard(lang),
            parse_mode="HTML"
        )
    else:
        await message.answer(
            f"✅ <b>Request sent!</b>\n\n"
            f"💰 Amount: {format_ton(data['amount'])} TON\n"
            f"📤 To receive: {format_ton(data['final_amount'])} TON\n\n"
            f"⏰ Awaiting admin confirmation.",
            reply_markup=get_back_keyboard(lang),
            parse_mode="HTML"
        )
    await state.clear()

# -------------------- АДМИН --------------------

@dp.message(Command("admin"))
async def admin_panel(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ Нет доступа")
        return
    
    await message.answer("👑 <b>ПАНЕЛЬ АДМИНИСТРАТОРА</b>", reply_markup=get_admin_keyboard(), parse_mode="HTML")

@dp.callback_query(F.data == "admin_add")
async def admin_add_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет доступа")
        return
    
    await state.set_state(AdminStates.waiting_user_id)
    await callback.message.edit_text("💰 <b>Введите ID пользователя:</b>", reply_markup=get_back_keyboard("ru"), parse_mode="HTML")
    await callback.answer()

@dp.message(AdminStates.waiting_user_id)
async def admin_get_user(message: Message, state: FSMContext):
    try:
        user_id = int(message.text.strip())
        user = get_user(user_id)
        if not user:
            await message.answer("❌ Пользователь не найден!")
            await state.clear()
            return
        await state.update_data(user_id=user_id)
        await state.set_state(AdminStates.waiting_amount)
        await message.answer(f"👤 {user['username']}\n💰 Баланс: {format_ton(user['balance'])} TON\n\n💰 <b>Введите сумму для начисления:</b>", parse_mode="HTML")
    except:
        await message.answer("❌ Неверный ID!")

@dp.message(AdminStates.waiting_amount)
async def admin_add_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text.strip())
        data = await state.get_data()
        update_balance(data["user_id"], amount)
        user = get_user(data["user_id"])
        await message.answer(f"✅ <b>Начислено {amount} TON</b>\n👤 {user['username']}\n💰 Новый баланс: {format_ton(user['balance'])} TON", parse_mode="HTML")
        await state.clear()
    except:
        await message.answer("❌ Неверная сумма!")

@dp.callback_query(F.data == "admin_withdrawals")
async def admin_withdrawals(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет доступа")
        return
    
    withdrawals = get_pending_withdrawals()
    
    if not withdrawals:
        await callback.message.edit_text("📭 <b>Нет активных заявок на вывод</b>", reply_markup=get_back_keyboard("ru"), parse_mode="HTML")
        await callback.answer()
        return
    
    for w in withdrawals:
        text = f"💸 <b>ЗАЯВКА #{w[0]}</b>\n\n"
        text += f"👤 ID: <code>{w[1]}</code>\n"
        text += f"💰 Сумма: {w[2]} TON\n"
        text += f"📍 Адрес: <code>{w[3]}</code>\n"
        text += f"📅 Создана: {w[5]}"
        
        await callback.message.answer(text, reply_markup=get_withdrawal_buttons(w[0]), parse_mode="HTML")
    
    await callback.message.delete()
    await callback.answer()

@dp.callback_query(F.data.startswith("approve_"))
async def approve_withdrawal(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет доступа")
        return
    
    withdraw_id = int(callback.data.split("_")[1])
    update_withdrawal_status(withdraw_id, "approved")
    
    await callback.message.edit_text("✅ <b>Вывод одобрен!</b>", parse_mode="HTML")
    await callback.answer()

@dp.callback_query(F.data.startswith("reject_"))
async def reject_withdrawal(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет доступа")
        return
    
    withdraw_id = int(callback.data.split("_")[1])
    update_withdrawal_status(withdraw_id, "rejected")
    
    await callback.message.edit_text("❌ <b>Вывод отклонён!</b>", parse_mode="HTML")
    await callback.answer()

@dp.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет доступа")
        return
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    users_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM workers")
    workers_count = cursor.fetchone()[0]
    cursor.execute("SELECT SUM(balance) FROM users")
    total_balance = cursor.fetchone()[0] or 0
    cursor.execute("SELECT COUNT(*) FROM withdrawals WHERE status='pending'")
    pending_withdrawals = cursor.fetchone()[0]
    conn.close()
    
    text = (
        f"╔══════════════════════════════════╗\n"
        f"║      📊 <b>СТАТИСТИКА БОТА</b>      ║\n"
        f"╚══════════════════════════════════╝\n\n"
        f"👥 <b>Пользователей:</b> {users_count}\n"
        f"👷 <b>Куплено рабочих:</b> {workers_count}\n"
        f"💰 <b>Всего баланс:</b> {format_ton(total_balance)} TON\n"
        f"⏳ <b>Заявок на вывод:</b> {pending_withdrawals}"
    )
    
    await callback.message.edit_text(text, reply_markup=get_back_keyboard("ru"), parse_mode="HTML")
    await callback.answer()

# -------------------- МАГАЗИН --------------------

@dp.callback_query(F.data == "menu_shop")
async def menu_shop(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    lang = user["language"] if user else "ru"
    
    if lang == "ru":
        text = (
            f"╔══════════════════════════════════╗\n"
            f"║         🏪 <b>МАГАЗИН</b>           ║\n"
            f"╚══════════════════════════════════╝\n\n"
            f"💰 <b>Ваш баланс:</b> {format_ton(user['balance'])} TON\n\n"
            f"👇 <b>Выберите рабочего для покупки:</b>"
        )
    else:
        text = (
            f"╔══════════════════════════════════╗\n"
            f"║         🏪 <b>SHOP</b>              ║\n"
            f"╚══════════════════════════════════╝\n\n"
            f"💰 <b>Your balance:</b> {format_ton(user['balance'])} TON\n\n"
            f"👇 <b>Choose a worker to buy:</b>"
        )
    
    await callback.message.edit_text(text, reply_markup=get_shop_keyboard(lang), parse_mode="HTML")
    await callback.answer()

@dp.callback_query(F.data.startswith("buy_"))
async def buy_worker(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    lang = user["language"] if user else "ru"
    worker_id = int(callback.data.split("_")[1])
    worker = WORKERS[worker_id]
    name = worker[f"name_{lang}"] if lang in worker else worker["name_ru"]
    
    if user["balance"] < worker["cost"]:
        await callback.answer(f"❌ " + ("Недостаточно средств!" if lang == "ru" else "Insufficient funds!"), show_alert=True)
        return
    
    update_balance(callback.from_user.id, -worker["cost"])
    add_worker(callback.from_user.id, worker_id)
    
    await callback.answer(f"✅ " + ("Куплен" if lang == "ru" else "Bought") + f" {name}!", show_alert=True)
    
    # Обновляем сообщение с магазином
    user = get_user(callback.from_user.id)
    if lang == "ru":
        text = (
            f"╔══════════════════════════════════╗\n"
            f"║         🏪 <b>МАГАЗИН</b>           ║\n"
            f"╚══════════════════════════════════╝\n\n"
            f"💰 <b>Ваш баланс:</b> {format_ton(user['balance'])} TON\n\n"
            f"👇 <b>Выберите рабочего для покупки:</b>"
        )
    else:
        text = (
            f"╔══════════════════════════════════╗\n"
            f"║         🏪 <b>SHOP</b>              ║\n"
            f"╚══════════════════════════════════╝\n\n"
            f"💰 <b>Your balance:</b> {format_ton(user['balance'])} TON\n\n"
            f"👇 <b>Choose a worker to buy:</b>"
        )
    
    await callback.message.edit_text(text, reply_markup=get_shop_keyboard(lang), parse_mode="HTML")

# -------------------- РАБОЧИЕ --------------------

@dp.callback_query(F.data == "menu_workers")
async def menu_workers(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    lang = user["language"] if user else "ru"
    user_id = callback.from_user.id
    workers = get_workers(user_id)
    income = calculate_income(user_id)
    pending = calculate_pending(user_id)
    
    if lang == "ru":
        text = (
            f"╔══════════════════════════════════╗\n"
            f"║       👷 <b>МОИ РАБОЧИЕ</b>         ║\n"
            f"╚══════════════════════════════════╝\n\n"
            f"💰 <b>Баланс:</b> {format_ton(user['balance'])} TON\n"
            f"📈 <b>Доход/день:</b> {format_ton(income)} TON\n"
            f"⏳ <b>Накоплено:</b> {format_ton(pending)} TON\n\n"
        )
    else:
        text = (
            f"╔══════════════════════════════════╗\n"
            f"║       👷 <b>MY WORKERS</b>          ║\n"
            f"╚══════════════════════════════════╝\n\n"
            f"💰 <b>Balance:</b> {format_ton(user['balance'])} TON\n"
            f"📈 <b>Income/day:</b> {format_ton(income)} TON\n"
            f"⏳ <b>Pending:</b> {format_ton(pending)} TON\n\n"
        )
    
    if not workers:
        text += "😔 " + ("У вас нет рабочих. Зайдите в магазин!" if lang == "ru" else "You have no workers. Go to the shop!")
    else:
        text += "📋 " + ("Список рабочих:" if lang == "ru" else "Workers list:") + "\n━━━━━━━━━━━━━━━━━━━━━━\n"
        for w in workers:
            worker_type = w[0]
            count = w[1]
            name = WORKERS[worker_type][f"name_{lang}"] if lang in WORKERS[worker_type] else WORKERS[worker_type]["name_ru"]
            income_day = WORKERS[worker_type]["income"] * count
            text += f"🔹 {name} ×{count}\n   └ 📊 {income_day:.4f} TON/день\n"
    
    await callback.message.edit_text(text, reply_markup=get_workers_keyboard(lang), parse_mode="HTML")
    await callback.answer()

@dp.callback_query(F.data == "collect")
async def collect_income(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    lang = user["language"] if user else "ru"
    user_id = callback.from_user.id
    pending = calculate_pending(user_id)
    
    if pending < 0.001:
        await callback.answer("⏰ " + ("Ещё нечего собирать!" if lang == "ru" else "Nothing to collect yet!"), show_alert=True)
        return
    
    update_balance(user_id, pending)
    update_last_collect(user_id)
    user = get_user(user_id)
    
    await callback.answer(f"✅ +{format_ton(pending)} TON", show_alert=True)
    
    # Обновляем список рабочих
    workers = get_workers(user_id)
    income = calculate_income(user_id)
    
    if lang == "ru":
        text = (
            f"╔══════════════════════════════════╗\n"
            f"║       👷 <b>МОИ РАБОЧИЕ</b>         ║\n"
            f"╚══════════════════════════════════╝\n\n"
            f"💰 <b>Баланс:</b> {format_ton(user['balance'])} TON\n"
            f"📈 <b>Доход/день:</b> {format_ton(income)} TON\n"
            f"⏳ <b>Накоплено:</b> 0 TON\n\n"
        )
    else:
        text = (
            f"╔══════════════════════════════════╗\n"
            f"║       👷 <b>MY WORKERS</b>          ║\n"
            f"╚══════════════════════════════════╝\n\n"
            f"💰 <b>Balance:</b> {format_ton(user['balance'])} TON\n"
            f"📈 <b>Income/day:</b> {format_ton(income)} TON\n"
            f"⏳ <b>Pending:</b> 0 TON\n\n"
        )
    
    if not workers:
        text += "😔 " + ("У вас нет рабочих. Зайдите в магазин!" if lang == "ru" else "You have no workers. Go to the shop!")
    else:
        text += "📋 " + ("Список рабочих:" if lang == "ru" else "Workers list:") + "\n━━━━━━━━━━━━━━━━━━━━━━\n"
        for w in workers:
            worker_type = w[0]
            count = w[1]
            name = WORKERS[worker_type][f"name_{lang}"] if lang in WORKERS[worker_type] else WORKERS[worker_type]["name_ru"]
            income_day = WORKERS[worker_type]["income"] * count
            text += f"🔹 {name} ×{count}\n   └ 📊 {income_day:.4f} TON/день\n"
    
    await callback.message.edit_text(text, reply_markup=get_workers_keyboard(lang), parse_mode="HTML")

# -------------------- ФЕРМА --------------------

@dp.callback_query(F.data == "menu_farm")
async def menu_farm(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    lang = user["language"] if user else "ru"
    level = user["farm_level"]
    farm = FARM_LEVELS[level]
    workers_count = get_worker_count(callback.from_user.id)
    
    stars = "⭐" * level + "☆" * (10 - level)
    
    if lang == "ru":
        text = (
            f"╔══════════════════════════════════╗\n"
            f"║         🌾 <b>ФЕРМА</b>             ║\n"
            f"╚══════════════════════════════════╝\n\n"
            f"📊 <b>Уровень:</b> {level}/10\n{stars}\n\n"
            f"👷 <b>Рабочих:</b> {workers_count}\n"
            f"🎁 <b>Бонус:</b> +{farm['bonus']}%\n\n"
        )
    else:
        text = (
            f"╔══════════════════════════════════╗\n"
            f"║         🌾 <b>FARM</b>              ║\n"
            f"╚══════════════════════════════════╝\n\n"
            f"📊 <b>Level:</b> {level}/10\n{stars}\n\n"
            f"👷 <b>Workers:</b> {workers_count}\n"
            f"🎁 <b>Bonus:</b> +{farm['bonus']}%\n\n"
        )
    
    if level < 10:
        next_farm = FARM_LEVELS[level + 1]
        if lang == "ru":
            text += (
                f"⬆️ <b>Следующий уровень:</b>\n"
                f"💰 Стоимость: {next_farm['cost']} TON\n"
                f"👷 Нужно рабочих: {next_farm['workers']}\n"
                f"🎁 Новый бонус: +{next_farm['bonus']}%"
            )
        else:
            text += (
                f"⬆️ <b>Next level:</b>\n"
                f"💰 Cost: {next_farm['cost']} TON\n"
                f"👷 Workers needed: {next_farm['workers']}\n"
                f"🎁 New bonus: +{next_farm['bonus']}%"
            )
    else:
        text += "🏆 " + ("Ферма полностью прокачана!" if lang == "ru" else "Farm is fully upgraded!")
    
    await callback.message.edit_text(text, reply_markup=get_farm_keyboard(user, lang), parse_mode="HTML")
    await callback.answer()

@dp.callback_query(F.data == "upgrade_farm")
async def upgrade_farm(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    lang = user["language"] if user else "ru"
    current_level = user["farm_level"]
    
    if current_level >= 10:
        await callback.answer("❌ " + ("Максимальный уровень!" if lang == "ru" else "Maximum level!"), show_alert=True)
        return
    
    next_level = current_level + 1
    next_farm = FARM_LEVELS[next_level]
    workers_count = get_worker_count(callback.from_user.id)
    
    if workers_count < next_farm["workers"]:
        await callback.answer(f"❌ " + ("Нужно" if lang == "ru" else "Need") + f" {next_farm['workers']} " + ("рабочих!" if lang == "ru" else "workers!"), show_alert=True)
        return
    
    if user["balance"] < next_farm["cost"]:
        await callback.answer(f"❌ " + ("Недостаточно средств! Нужно:" if lang == "ru" else "Insufficient funds! Need:") + f" {next_farm['cost']} TON", show_alert=True)
        return
    
    update_balance(callback.from_user.id, -next_farm["cost"])
    update_farm_level(callback.from_user.id, next_level)
    
    await callback.answer(f"✅ " + ("Ферма улучшена до" if lang == "ru" else "Farm upgraded to") + f" {next_level} " + ("уровня!" if lang == "ru" else "level!"), show_alert=True)
    await menu_farm(callback)

# -------------------- ЕЖЕДНЕВНЫЙ БОНУС --------------------

@dp.callback_query(F.data == "menu_daily")
async def menu_daily(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    lang = user["language"] if user else "ru"
    user_id = callback.from_user.id
    
    today = datetime.now().date().isoformat()
    streak = user["streak"]
    last_daily = user["last_daily"]
    
    if last_daily:
        if last_daily == today:
            if lang == "ru":
                text = (
                    f"╔══════════════════════════════════╗\n"
                    f"║        🎁 <b>БОНУС</b>              ║\n"
                    f"╚══════════════════════════════════╝\n\n"
                    f"⏰ <b>Вы уже получили бонус сегодня!</b>\n"
                    f"🔥 Серия: {streak} дней\n\n"
                    f"💎 Завтра: +{get_daily_bonus(streak + 1)} TON"
                )
            else:
                text = (
                    f"╔══════════════════════════════════╗\n"
                    f"║        🎁 <b>BONUS</b>              ║\n"
                    f"╚══════════════════════════════════╝\n\n"
                    f"⏰ <b>You already claimed today's bonus!</b>\n"
                    f"🔥 Streak: {streak} days\n\n"
                    f"💎 Tomorrow: +{get_daily_bonus(streak + 1)} TON"
                )
            await callback.message.edit_text(text, reply_markup=get_back_keyboard(lang), parse_mode="HTML")
            await callback.answer()
            return
        elif (datetime.now().date() - datetime.fromisoformat(last_daily).date()).days > 1:
            streak = 0
    
    streak += 1
    bonus = get_daily_bonus(streak)
    
    update_balance(user_id, bonus)
    update_daily_streak(user_id, streak, today)
    user = get_user(user_id)
    bar = get_streak_bar(streak)
    
    if lang == "ru":
        text = (
            f"╔══════════════════════════════════╗\n"
            f"║        🎁 <b>БОНУС</b>              ║\n"
            f"╚══════════════════════════════════╝\n\n"
            f"✅ <b>Бонус получен!</b>\n\n"
            f"💰 +{bonus} TON\n"
            f"💳 Баланс: {format_ton(user['balance'])} TON\n\n"
            f"🔥 Серия: {streak} дней\n"
            f"{bar}\n\n"
            f"💎 Завтра: +{get_daily_bonus(streak + 1)} TON"
        )
    else:
        text = (
            f"╔══════════════════════════════════╗\n"
            f"║        🎁 <b>BONUS</b>              ║\n"
            f"╚══════════════════════════════════╝\n\n"
            f"✅ <b>Bonus claimed!</b>\n\n"
            f"💰 +{bonus} TON\n"
            f"💳 Balance: {format_ton(user['balance'])} TON\n\n"
            f"🔥 Streak: {streak} days\n"
            f"{bar}\n\n"
            f"💎 Tomorrow: +{get_daily_bonus(streak + 1)} TON"
        )
    
    await callback.message.edit_text(text, reply_markup=get_back_keyboard(lang), parse_mode="HTML")
    await callback.answer()

# -------------------- РЕФЕРАЛЫ --------------------

@dp.callback_query(F.data == "menu_referral")
async def menu_referral(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    lang = user["language"] if user else "ru"
    user_id = callback.from_user.id
    bot_info = await bot.get_me()
    link = f"https://t.me/{bot_info.username}?start={user_id}"
    
    ref_count = get_referrals_count(user_id)
    
    if lang == "ru":
        text = (
            f"╔══════════════════════════════════╗\n"
            f"║        👥 <b>РЕФЕРАЛЫ</b>           ║\n"
            f"╚══════════════════════════════════╝\n\n"
            f"👥 <b>Рефералов:</b> {ref_count}\n\n"
            f"🔗 <b>Ваша реферальная ссылка:</b>\n<code>{link}</code>\n\n"
            f"📊 <b>Вы получаете 7% от дохода ваших рефералов!</b>\n"
            f"🎁 <b>Бонус за приглашённого:</b> +{REFERRAL_BONUS} TON"
        )
    else:
        text = (
            f"╔══════════════════════════════════╗\n"
            f"║        👥 <b>REFERRALS</b>          ║\n"
            f"╚══════════════════════════════════╝\n\n"
            f"👥 <b>Referrals:</b> {ref_count}\n\n"
            f"🔗 <b>Your referral link:</b>\n<code>{link}</code>\n\n"
            f"📊 <b>You get 7% from your referrals' income!</b>\n"
            f"🎁 <b>Bonus per referral:</b> +{REFERRAL_BONUS} TON"
        )
    
    await callback.message.edit_text(text, reply_markup=get_back_keyboard(lang), parse_mode="HTML")
    await callback.answer()

# -------------------- ТОП --------------------

@dp.callback_query(F.data == "menu_top")
async def menu_top(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    lang = user["language"] if user else "ru"
    top = get_top_players()
    
    if lang == "ru":
        text = (
            f"╔══════════════════════════════════╗\n"
            f"║        🏆 <b>ТОП ИГРОКОВ</b>         ║\n"
            f"╚══════════════════════════════════╝\n\n"
        )
    else:
        text = (
            f"╔══════════════════════════════════╗\n"
            f"║        🏆 <b>TOP PLAYERS</b>        ║\n"
            f"╚══════════════════════════════════╝\n\n"
        )
    
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    
    for i, player in enumerate(top):
        name = player[0] or "Аноним" if lang == "ru" else "Anonymous"
        if i < len(medals):
            text += f"{medals[i]} {name} — {format_ton(player[1])} TON\n"
        else:
            text += f"{i+1}️⃣ {name} — {format_ton(player[1])} TON\n"
    
    await callback.message.edit_text(text, reply_markup=get_back_keyboard(lang), parse_mode="HTML")
    await callback.answer()

# -------------------- ЯЗЫК --------------------

@dp.callback_query(F.data == "menu_language")
async def menu_language(callback: CallbackQuery):
    await callback.message.edit_text("🌍 <b>Выберите язык / Choose language:</b>", reply_markup=get_language_keyboard(), parse_mode="HTML")
    await callback.answer()

@dp.callback_query(F.data == "lang_ru")
async def set_lang_ru(callback: CallbackQuery):
    update_user_language(callback.from_user.id, "ru")
    await callback.answer("✅ Язык изменён на Русский!")
    await back_to_menu(callback)

@dp.callback_query(F.data == "lang_en")
async def set_lang_en(callback: CallbackQuery):
    update_user_language(callback.from_user.id, "en")
    await callback.answer("✅ Language changed to English!")
    await back_to_menu(callback)

# ==================== ЗАПУСК ====================

async def main():
    init_db()
    print("✅ База данных инициализирована")
    
    asyncio.create_task(start_payment_checker())
    
    print("🚀 Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
