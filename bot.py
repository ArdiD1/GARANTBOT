import logging
import sqlite3
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils import executor

API_TOKEN = '7686571543:AAFGahVHwioS0LNmN2dWsDJvZXQ5lk3WTk0'
ADMIN_ID = 5141765726

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

conn = sqlite3.connect("database.db")
cursor = conn.cursor()
cursor.executescript("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    balance REAL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS deals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    buyer_id INTEGER,
    seller_id INTEGER,
    amount REAL,
    status TEXT
);
""")
conn.commit()

def get_balance(user_id):
    cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    return row[0] if row else 0

def update_balance(user_id, amount):
    cursor.execute("INSERT INTO users (user_id, balance) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET balance = balance + ?",
                   (user_id, amount, amount))
    conn.commit()

@dp.message_handler(commands=['start'])
async def start_cmd(message: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton("💰 Пополнить баланс", callback_data="deposit")],
        [InlineKeyboardButton("📦 Создать сделку", callback_data="create_deal")],
        [InlineKeyboardButton("💼 Баланс", callback_data="balance")]
    ])
    await message.answer("Добро пожаловать в гарант-бота!", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data == "balance")
async def show_balance(callback: types.CallbackQuery):
    balance = get_balance(callback.from_user.id)
    await callback.answer()
    await callback.message.answer(f"Ваш баланс: {balance:.2f} USDT")

@dp.callback_query_handler(lambda c: c.data == "deposit")
async def deposit_instruction(callback: types.CallbackQuery):
    await callback.answer()
    await callback.message.answer(
        "🔐 Отправьте TON/USDT вручную на ваш криптокошелёк и пришлите сюда чек (фото или текст).
💬 Бот передаст его администратору для ручной активации."
    )

@dp.message_handler(content_types=types.ContentTypes.ANY)
async def handle_check(message: types.Message):
    if message.content_type in ['text', 'photo', 'document']:
        await message.reply("✅ Чек передан администратору. Ожидайте подтверждения.")
        await bot.send_message(ADMIN_ID, f"Поступил чек от @{message.from_user.username or message.from_user.id}:")
        await message.forward(ADMIN_ID)

@dp.message_handler(commands=['add'])
async def add_balance_cmd(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        user_id, amount = message.text.split()[1:]
        user_id = int(user_id)
        amount = float(amount)
        update_balance(user_id, amount)
        await message.reply(f"💰 Баланс пользователя {user_id} пополнен на {amount} USDT.")
    except:
        await message.reply("❌ Пример: /add 123456789 10.5")

@dp.callback_query_handler(lambda c: c.data == "create_deal")
async def create_deal(callback: types.CallbackQuery):
    await callback.answer()
    await callback.message.answer(
        "Отправь username продавца (с @) и сумму сделки через пробел\n"
        "Пример: `@seller 5.00`",
        parse_mode="Markdown"
    )

@dp.message_handler(lambda message: len(message.text.split()) == 2 and message.text.split()[1].replace('.', '', 1).isdigit())
async def handle_deal_data(message: types.Message):
    try:
        username, amount = message.text.split()
        amount = float(amount)
        buyer_id = message.from_user.id
        username = username.lstrip("@")
        seller = await bot.get_chat(username)
        seller_id = seller.id

        balance = get_balance(buyer_id)
        if balance < amount:
            await message.reply("❌ Недостаточно средств.")
            return
        update_balance(buyer_id, -amount)
        cursor.execute("INSERT INTO deals (buyer_id, seller_id, amount, status) VALUES (?, ?, ?, ?)",
                       (buyer_id, seller_id, amount, "hold"))
        conn.commit()

        kb = InlineKeyboardMarkup().add(InlineKeyboardButton("✅ Подтвердить получение", callback_data=f"confirm_{seller_id}_{amount}"))
        await message.reply(
            f"✅ Сделка создана!
Продавец @{username} получит {amount} USDT после подтверждения.",
            reply_markup=kb
        )
    except Exception as e:
        await message.reply("⚠️ Ошибка: убедитесь, что продавец существует и написал боту.")
        print(f"Ошибка: {e}")

@dp.callback_query_handler(lambda c: c.data.startswith("confirm_"))
async def confirm_deal(callback: types.CallbackQuery):
    try:
        _, seller_id, amount = callback.data.split("_")
        seller_id = int(seller_id)
        amount = float(amount)
        buyer_id = callback.from_user.id

        cursor.execute("SELECT id, status FROM deals WHERE buyer_id = ? AND seller_id = ? AND amount = ? AND status = 'hold'",
                       (buyer_id, seller_id, amount))
        deal = cursor.fetchone()
        if not deal:
            await callback.message.answer("❌ Сделка не найдена или уже подтверждена.")
            return

        update_balance(seller_id, amount)
        cursor.execute("UPDATE deals SET status = 'done' WHERE id = ?", (deal[0],))
        conn.commit()

        await callback.message.answer(f"✅ Сделка завершена. Продавцу переведено {amount} USDT.")
        await bot.send_message(seller_id, f"💰 Вам поступил платёж {amount} USDT от покупателя.")
    except Exception as e:
        await callback.message.answer("⚠️ Ошибка при подтверждении.")
        print(f"Ошибка подтверждения: {e}")

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    executor.start_polling(dp, skip_updates=True)