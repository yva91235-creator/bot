import asyncio
import sqlite3
from datetime import datetime
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

WORKERS = {
    1: {"name": "🧑‍🌾 Стажёр", "cost": 1, "income": 0.003},
    2: {"name": "👨‍🔧 Разнорабочий", "cost": 5, "income": 0.02},
    3: {"name": "👷 Шахтёр", "cost": 20, "income": 0.10},
    4: {"name": "🔧 Инженер", "cost": 50, "income": 0.30},
    5: {"name": "🧙‍♂️ Бурильщик", "cost": 100, "income": 0.70},
    6: {"name": "⚙️ Механик", "cost": 200, "income": 1.60},
    7: {"name": "🏭 Директор шахты", "cost": 500, "income": 4.50},
    8: {"name": "👑 Магнат", "cost": 1000, "income": 10.00},
    9: {"name": "⭐ Олигарх", "cost": 2500, "income": 30.00},
    10: {"name": "💎 Крипто-король", "cost": 5000, "income": 75.00},
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
            referred_by INTEGER
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
            "referred_by": row[7]
        }
    return None

def create_user(user_id, username, referred_by=None):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR IGNORE INTO users (user_id, username, last_collect, referred_by)
        VALUES (?, ?, ?, ?)
    ''', (user_id, username, datetime.now().isoformat(), referred_by))
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

# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================

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
    
    last_collect = datetime.fromisoformat(user["last_collect"])
    income_day = calculate_income(user_id)
    hours_passed = (datetime.now() - last_collect).total_seconds() / 3600
    pending = income_day * (hours_passed / 24)
    
    return round(pending, 4)

def format_ton(amount):
    return f"{amount:.3f}"

# ==================== КЛАВИАТУРЫ ====================

def get_main_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 Профиль", callback_data="menu_profile")],
        [InlineKeyboardButton(text="🏪 Магазин", callback_data="menu_shop")],
        [InlineKeyboardButton(text="👷 Мои рабочие", callback_data="menu_workers")],
        [InlineKeyboardButton(text="🌾 Ферма", callback_data="menu_farm")],
        [InlineKeyboardButton(text="🎁 Бонус", callback_data="menu_daily")],
        [InlineKeyboardButton(text="👥 Рефералы", callback_data="menu_referral")],
        [InlineKeyboardButton(text="🏆 Топ", callback_data="menu_top")],
    ])

def get_back_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_menu")]
    ])

def get_shop_keyboard():
    buttons = []
    for wid, w in WORKERS.items():
        buttons.append([InlineKeyboardButton(
            text=f"{w['name']} — {w['cost']} TON",
            callback_data=f"buy_{wid}"
        )])
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_workers_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Собрать доход", callback_data="collect")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_menu")],
    ])

def get_farm_keyboard(user):
    buttons = []
    current_level = user["farm_level"]
    if current_level < 10:
        next_level = FARM_LEVELS[current_level + 1]
        if user["total_workers"] >= next_level["workers"] and user["balance"] >= next_level["cost"]:
            buttons.append([InlineKeyboardButton(
                text=f"⬆️ Улучшить ({next_level['cost']} TON)",
                callback_data="upgrade_farm"
            )])
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_profile_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 Пополнить", callback_data="menu_deposit")],
        [InlineKeyboardButton(text="💸 Вывести", callback_data="menu_withdraw")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_menu")],
    ])

def get_deposit_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 10 TON", callback_data="deposit_10")],
        [InlineKeyboardButton(text="💎 25 TON", callback_data="deposit_25")],
        [InlineKeyboardButton(text="💎 50 TON", callback_data="deposit_50")],
        [InlineKeyboardButton(text="💎 100 TON", callback_data="deposit_100")],
        [InlineKeyboardButton(text="💎 250 TON", callback_data="deposit_250")],
        [InlineKeyboardButton(text="💎 500 TON", callback_data="deposit_500")],
        [InlineKeyboardButton(text="💎 1000 TON", callback_data="deposit_1000")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_menu")],
    ])

def get_withdraw_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💸 Вывести", callback_data="withdraw_start")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_menu")],
    ])

def get_admin_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Начислить баланс", callback_data="admin_add")],
        [InlineKeyboardButton(text="✅ Заявки на вывод", callback_data="admin_withdrawals")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
    ])

def get_withdrawal_buttons(withdraw_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Одобрить", callback_data=f"approve_{withdraw_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{withdraw_id}"),
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
    if not user:
        args = message.text.split()
        ref_id = None
        if len(args) > 1:
            try:
                ref_id = int(args[1])
                if ref_id == user_id:
                    ref_id = None
            except:
                pass
        create_user(user_id, username, ref_id)
        
        if ref_id:
            update_balance(ref_id, 0.5)
    
    await show_main_menu(message)

async def show_main_menu(message: Message):
    user_id = message.from_user.id
    user = get_user(user_id)
    income = calculate_income(user_id)
    pending = calculate_pending(user_id)
    
    text = f"🏭 <b>WORKERS ON TON</b>\n\n"
    text += f"👤 {user['username'] or 'User'}\n"
    text += f"💰 Баланс: {format_ton(user['balance'])} TON\n"
    text += f"📈 Доход/день: {format_ton(income)} TON\n"
    text += f"👷 Рабочих: {user['total_workers']}\n"
    text += f"🌾 Уровень фермы: {user['farm_level']}/10\n"
    text += f"⏳ Накоплено: {format_ton(pending)} TON\n\n"
    text += f"👇 Выберите действие:"
    
    await message.answer(text, reply_markup=get_main_keyboard(), parse_mode="HTML")

@dp.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = get_user(user_id)
    income = calculate_income(user_id)
    pending = calculate_pending(user_id)
    
    text = f"🏭 <b>WORKERS ON TON</b>\n\n"
    text += f"👤 {user['username'] or 'User'}\n"
    text += f"💰 Баланс: {format_ton(user['balance'])} TON\n"
    text += f"📈 Доход/день: {format_ton(income)} TON\n"
    text += f"👷 Рабочих: {user['total_workers']}\n"
    text += f"🌾 Уровень фермы: {user['farm_level']}/10\n"
    text += f"⏳ Накоплено: {format_ton(pending)} TON\n\n"
    text += f"👇 Выберите действие:"
    
    await callback.message.edit_text(text, reply_markup=get_main_keyboard(), parse_mode="HTML")
    await callback.answer()

# -------------------- ПРОФИЛЬ --------------------

@dp.callback_query(F.data == "menu_profile")
async def menu_profile(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = get_user(user_id)
    
    text = f"👤 <b>ПРОФИЛЬ</b>\n\n"
    text += f"🆔 ID: {user_id}\n"
    text += f"👤 Имя: {user['username'] or 'Не указано'}\n"
    text += f"💰 Баланс: {format_ton(user['balance'])} TON\n"
    text += f"👷 Рабочих: {user['total_workers']}\n"
    text += f"🌾 Уровень фермы: {user['farm_level']}/10\n"
    text += f"📈 Доход/день: {format_ton(calculate_income(user_id))} TON"
    
    await callback.message.edit_text(text, reply_markup=get_profile_keyboard(), parse_mode="HTML")
    await callback.answer()

# -------------------- ПОПОЛНЕНИЕ --------------------

@dp.callback_query(F.data == "menu_deposit")
async def menu_deposit(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    
    text = f"💎 <b>ПОПОЛНЕНИЕ БАЛАНСА</b>\n\n"
    text += f"💰 Ваш баланс: {format_ton(user['balance'])} TON\n\n"
    text += "Выберите сумму для пополнения:"
    
    await callback.message.edit_text(text, reply_markup=get_deposit_keyboard(), parse_mode="HTML")
    await callback.answer()

@dp.callback_query(F.data.startswith("deposit_"))
async def deposit_amount(callback: CallbackQuery):
    amount = int(callback.data.split("_")[1])
    
    text = f"💎 <b>ОПЛАТА</b>\n\n"
    text += f"💰 Сумма: {amount} TON\n\n"
    text += "━━━━━━━━━━━━━━━━━━━━━━\n"
    text += f"📤 Отправьте перевод на кошелёк:\n\n"
    text += f"💎 TON:\n<code>{TON_WALLET}</code>\n\n"
    text += f"💵 USDT (TRC20):\n<code>{USDT_WALLET}</code>\n\n"
    text += "━━━━━━━━━━━━━━━━━━━━━━\n"
    text += f"📩 По вопросам: {SUPPORT_USERNAME}\n\n"
    text += "После оплаты напишите администратору @MollyWhip1"
    
    await callback.message.edit_text(text, reply_markup=get_back_keyboard(), parse_mode="HTML")
    await callback.answer()

# -------------------- ВЫВОД --------------------

@dp.callback_query(F.data == "menu_withdraw")
async def menu_withdraw(callback: CallbackQuery, state: FSMContext):
    user = get_user(callback.from_user.id)
    
    text = f"💸 <b>ВЫВОД СРЕДСТВ</b>\n\n"
    text += f"💰 Доступно: {format_ton(user['balance'])} TON\n"
    text += f"📋 Минимум: {WITHDRAW_MIN} TON\n"
    text += f"💸 Комиссия: {int(WITHDRAW_FEE * 100)}%\n\n"
    text += f"Введите сумму для вывода:"
    
    await callback.message.edit_text(text, reply_markup=get_back_keyboard(), parse_mode="HTML")
    await state.set_state(WithdrawStates.waiting_amount)
    await callback.answer()

@dp.message(WithdrawStates.waiting_amount)
async def withdraw_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text.strip())
    except:
        await message.answer("❌ Введите корректное число!")
        return
    
    user = get_user(message.from_user.id)
    
    if amount < WITHDRAW_MIN:
        await message.answer(f"❌ Минимальная сумма вывода: {WITHDRAW_MIN} TON")
        return
    
    if amount > user["balance"]:
        await message.answer(f"❌ Недостаточно средств! Доступно: {format_ton(user['balance'])} TON")
        return
    
    fee = amount * WITHDRAW_FEE
    final_amount = amount - fee
    
    await state.update_data(amount=amount, fee=fee, final_amount=final_amount)
    await state.set_state(WithdrawStates.waiting_address)
    
    await message.answer(
        f"💰 Сумма: {format_ton(amount)} TON\n"
        f"💸 Комиссия ({int(WITHDRAW_FEE*100)}%): {format_ton(fee)} TON\n"
        f"📤 К выплате: {format_ton(final_amount)} TON\n\n"
        f"📝 Введите адрес TON кошелька:"
    )

@dp.message(WithdrawStates.waiting_address)
async def withdraw_address(message: Message, state: FSMContext):
    address = message.text.strip()
    data = await state.get_data()
    
    withdraw_id = create_withdrawal(message.from_user.id, data["amount"], address)
    update_balance(message.from_user.id, -data["amount"])
    
    # Уведомление админу
    for admin_id in ADMIN_IDS:
        try:
            admin_text = f"💸 НОВАЯ ЗАЯВКА НА ВЫВОД\n\n👤 {message.from_user.id}\n💰 Сумма: {data['amount']} TON\n📤 К выплате: {data['final_amount']} TON\n📍 Адрес: {address}"
            await bot.send_message(admin_id, admin_text, reply_markup=get_withdrawal_buttons(withdraw_id))
        except:
            pass
    
    await message.answer(
        f"✅ Заявка на вывод отправлена!\n\n"
        f"💰 Сумма: {format_ton(data['amount'])} TON\n"
        f"📤 К выплате: {format_ton(data['final_amount'])} TON\n\n"
        f"⏰ Ожидайте подтверждения администратора.",
        reply_markup=get_back_keyboard()
    )
    await state.clear()

# -------------------- АДМИН --------------------

@dp.message(Command("admin"))
async def admin_panel(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ Нет доступа")
        return
    
    await message.answer("👑 Панель администратора", reply_markup=get_admin_keyboard())

@dp.callback_query(F.data == "admin_add")
async def admin_add_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет доступа")
        return
    
    await state.set_state(AdminStates.waiting_user_id)
    await callback.message.edit_text("💰 Введите ID пользователя:", reply_markup=get_back_keyboard())
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
        await message.answer(f"👤 {user['username']}\n💰 Баланс: {format_ton(user['balance'])} TON\n\nВведите сумму для начисления:")
    except:
        await message.answer("❌ Неверный ID!")

@dp.message(AdminStates.waiting_amount)
async def admin_add_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text.strip())
        data = await state.get_data()
        update_balance(data["user_id"], amount)
        user = get_user(data["user_id"])
        await message.answer(f"✅ Начислено {amount} TON\n👤 {user['username']}\n💰 Новый баланс: {format_ton(user['balance'])} TON")
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
        await callback.message.edit_text("📭 Нет активных заявок на вывод", reply_markup=get_back_keyboard())
        await callback.answer()
        return
    
    for w in withdrawals:
        text = f"💸 ЗАЯВКА #{w[0]}\n\n"
        text += f"👤 ID: {w[1]}\n"
        text += f"💰 Сумма: {w[2]} TON\n"
        text += f"📍 Адрес: {w[3]}\n"
        text += f"📅 Создана: {w[5]}"
        
        await callback.message.answer(text, reply_markup=get_withdrawal_buttons(w[0]))
    
    await callback.message.delete()
    await callback.answer()

@dp.callback_query(F.data.startswith("approve_"))
async def approve_withdrawal(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет доступа")
        return
    
    withdraw_id = int(callback.data.split("_")[1])
    update_withdrawal_status(withdraw_id, "approved")
    
    await callback.message.edit_text("✅ Вывод одобрен!")
    await callback.answer()

@dp.callback_query(F.data.startswith("reject_"))
async def reject_withdrawal(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет доступа")
        return
    
    withdraw_id = int(callback.data.split("_")[1])
    w = get_pending_withdrawals()
    update_withdrawal_status(withdraw_id, "rejected")
    
    # Возвращаем средства
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, amount FROM withdrawals WHERE id = ?", (withdraw_id,))
    row = cursor.fetchone()
    if row:
        update_balance(row[0], row[1])
    conn.close()
    
    await callback.message.edit_text("❌ Вывод отклонён! Средства возвращены.")
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
    
    text = f"📊 <b>СТАТИСТИКА БОТА</b>\n\n"
    text += f"👥 Пользователей: {users_count}\n"
    text += f"👷 Куплено рабочих: {workers_count}\n"
    text += f"💰 Всего баланс: {format_ton(total_balance)} TON\n"
    text += f"⏳ Заявок на вывод: {pending_withdrawals}"
    
    await callback.message.edit_text(text, reply_markup=get_back_keyboard(), parse_mode="HTML")
    await callback.answer()

# -------------------- МАГАЗИН --------------------

@dp.callback_query(F.data == "menu_shop")
async def menu_shop(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    
    text = f"🏪 <b>МАГАЗИН</b>\n\n"
    text += f"💰 Баланс: {format_ton(user['balance'])} TON\n\n"
    text += f"👇 Выберите рабочего:"
    
    await callback.message.edit_text(text, reply_markup=get_shop_keyboard(), parse_mode="HTML")
    await callback.answer()

@dp.callback_query(F.data.startswith("buy_"))
async def buy_worker(callback: CallbackQuery):
    worker_id = int(callback.data.split("_")[1])
    worker = WORKERS[worker_id]
    user = get_user(callback.from_user.id)
    
    if user["balance"] < worker["cost"]:
        await callback.answer(f"❌ Недостаточно средств! Нужно: {worker['cost']} TON", show_alert=True)
        return
    
    update_balance(callback.from_user.id, -worker["cost"])
    add_worker(callback.from_user.id, worker_id)
    
    await callback.answer(f"✅ Вы купили {worker['name']}!", show_alert=True)
    await menu_shop(callback)

# -------------------- РАБОЧИЕ --------------------

@dp.callback_query(F.data == "menu_workers")
async def menu_workers(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = get_user(user_id)
    workers = get_workers(user_id)
    income = calculate_income(user_id)
    pending = calculate_pending(user_id)
    
    text = f"👷 <b>МОИ РАБОЧИЕ</b>\n\n"
    text += f"💰 Баланс: {format_ton(user['balance'])} TON\n"
    text += f"📈 Доход/день: {format_ton(income)} TON\n"
    text += f"⏳ Накоплено: {format_ton(pending)} TON\n\n"
    
    if not workers:
        text += "😔 У вас нет рабочих. Зайдите в магазин!"
    else:
        text += "📋 Список рабочих:\n━━━━━━━━━━━━━━━━━━━━━━\n"
        for w in workers:
            worker_type = w[0]
            count = w[1]
            name = WORKERS[worker_type]["name"]
            income_day = WORKERS[worker_type]["income"] * count
            text += f"{name} ×{count}\n└ {income_day:.4f} TON/день\n"
    
    await callback.message.edit_text(text, reply_markup=get_workers_keyboard(), parse_mode="HTML")
    await callback.answer()

@dp.callback_query(F.data == "collect")
async def collect_income(callback: CallbackQuery):
    user_id = callback.from_user.id
    pending = calculate_pending(user_id)
    
    if pending < 0.001:
        await callback.answer("⏰ Ещё нечего собирать!", show_alert=True)
        return
    
    update_balance(user_id, pending)
    update_last_collect(user_id)
    user = get_user(user_id)
    
    await callback.answer(f"✅ Собрано {format_ton(pending)} TON!", show_alert=True)
    await menu_workers(callback)

# -------------------- ФЕРМА --------------------

@dp.callback_query(F.data == "menu_farm")
async def menu_farm(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    level = user["farm_level"]
    farm = FARM_LEVELS[level]
    workers_count = get_worker_count(callback.from_user.id)
    
    stars = "⭐" * level + "☆" * (10 - level)
    
    text = f"🌾 <b>ФЕРМА</b>\n\n"
    text += f"📊 Уровень: {level}/10\n{stars}\n\n"
    text += f"👷 Рабочих: {workers_count}\n"
    text += f"🎁 Бонус: +{farm['bonus']}%\n\n"
    
    if level < 10:
        next_farm = FARM_LEVELS[level + 1]
        text += f"⬆️ Следующий уровень:\n"
        text += f"💰 Стоимость: {next_farm['cost']} TON\n"
        text += f"👷 Нужно рабочих: {next_farm['workers']}\n"
        text += f"🎁 Новый бонус: +{next_farm['bonus']}%"
    else:
        text += "🏆 Ферма полностью прокачана!"
    
    await callback.message.edit_text(text, reply_markup=get_farm_keyboard(user), parse_mode="HTML")
    await callback.answer()

@dp.callback_query(F.data == "upgrade_farm")
async def upgrade_farm(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    current_level = user["farm_level"]
    
    if current_level >= 10:
        await callback.answer("Максимальный уровень!", show_alert=True)
        return
    
    next_level = current_level + 1
    next_farm = FARM_LEVELS[next_level]
    workers_count = get_worker_count(callback.from_user.id)
    
    if workers_count < next_farm["workers"]:
        await callback.answer(f"❌ Нужно {next_farm['workers']} рабочих!", show_alert=True)
        return
    
    if user["balance"] < next_farm["cost"]:
        await callback.answer(f"❌ Недостаточно средств! Нужно: {next_farm['cost']} TON", show_alert=True)
        return
    
    update_balance(callback.from_user.id, -next_farm["cost"])
    update_farm_level(callback.from_user.id, next_level)
    
    await callback.answer(f"✅ Ферма улучшена до {next_level} уровня!", show_alert=True)
    await menu_farm(callback)

# -------------------- ЕЖЕДНЕВНЫЙ БОНУС --------------------

@dp.callback_query(F.data == "menu_daily")
async def menu_daily(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    
    bonus = 0.05
    streak = user["streak"] + 1
    
    update_balance(callback.from_user.id, bonus)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET streak = ? WHERE user_id = ?", (streak, callback.from_user.id))
    conn.commit()
    conn.close()
    
    text = f"🎁 <b>ЕЖЕДНЕВНЫЙ БОНУС</b>\n\n"
    text += f"✅ Бонус получен!\n\n"
    text += f"💰 +{bonus} TON\n"
    text += f"🔥 Серия: {streak} дней"
    
    await callback.message.edit_text(text, reply_markup=get_back_keyboard(), parse_mode="HTML")
    await callback.answer()

# -------------------- РЕФЕРАЛЫ --------------------

@dp.callback_query(F.data == "menu_referral")
async def menu_referral(callback: CallbackQuery):
    user_id = callback.from_user.id
    bot_info = await bot.get_me()
    link = f"https://t.me/{bot_info.username}?start={user_id}"
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users WHERE referred_by = ?", (user_id,))
    ref_count = cursor.fetchone()[0]
    conn.close()
    
    text = f"👥 <b>РЕФЕРАЛЬНАЯ ПРОГРАММА</b>\n\n"
    text += f"👥 Рефералов: {ref_count}\n\n"
    text += f"🔗 Ваша ссылка:\n<code>{link}</code>\n\n"
    text += f"📊 Вы получаете 7% от дохода ваших рефералов!"
    
    await callback.message.edit_text(text, reply_markup=get_back_keyboard(), parse_mode="HTML")
    await callback.answer()

# -------------------- ТОП --------------------

@dp.callback_query(F.data == "menu_top")
async def menu_top(callback: CallbackQuery):
    top = get_top_players()
    
    text = f"🏆 <b>ТОП ИГРОКОВ</b>\n\n"
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    
    for i, player in enumerate(top):
        if i < len(medals):
            text += f"{medals[i]} {player[0] or 'Аноним'} — {format_ton(player[1])} TON\n"
        else:
            text += f"{i+1}. {player[0] or 'Аноним'} — {format_ton(player[1])} TON\n"
    
    await callback.message.edit_text(text, reply_markup=get_back_keyboard(), parse_mode="HTML")
    await callback.answer()

# ==================== ЗАПУСК ====================

async def main():
    init_db()
    print("✅ База данных инициализирована")
    print("🚀 Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
