import os
import sqlite3
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor

API_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))  # Если не нужен — можно удалить эту строку

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

conn = sqlite3.connect("database.db")
cursor = conn.cursor()

cursor.execute('''CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    balance REAL DEFAULT 0
)''')

cursor.execute('''CREATE TABLE IF NOT EXISTS deals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    buyer_id INTEGER,
    seller_id INTEGER,
    amount REAL,
    status TEXT
)''')

conn.commit()

def get_balance(user_id):
    cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    return row[0] if row else 0

def update_balance(user_id, amount):
    cursor.execute("INSERT INTO users (user_id, balance) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET balance = balance + ?",
                   (user_id, amount, amount))
    conn.commit()

@dp.message_handler(commands=["start"])
async def start(msg: types.Message):
    await msg.reply("Добро пожаловать! Используй кнопки для управления.")

@dp.message_handler(commands=["balance"])
async def show_balance(msg: types.Message):
    balance = get_balance(msg.from_user.id)
    await msg.reply(f"💰 Ваш баланс: {balance:.2f} USDT")

@dp.message_handler(commands=["topup"])
async def topup(msg: types.Message):
    await msg.reply(
        "🔐 Отправьте TON/USDT вручную на ваш криптокошелёк и пришлите сюда чек (фото или текст).\n"
        "💬 После этого введите сумму числом, чтобы бот пополнил баланс."
    )


@dp.message_handler(lambda msg: msg.text.replace('.', '', 1).isdigit())
async def confirm_topup(msg: types.Message):
    amount = float(msg.text)
    update_balance(msg.from_user.id, amount)
    await msg.reply(f"✅ Баланс пополнен на {amount:.2f} USDT.")

@dp.message_handler(commands=["deal"])
async def create_deal(msg: types.Message):
    await msg.reply(
await msg.reply(
    "Отправьте тег продавца (без @) и сумму, например:\n"
    "`sellerusername 25.5`",
    parse_mode="Markdown"
)

@dp.message_handler(lambda msg: len(msg.text.split()) == 2)
async def process_deal(msg: types.Message):
    try:
        seller_username, amount = msg.text.split()
        amount = float(amount)
        buyer_id = msg.from_user.id
        seller_id = abs(hash(seller_username)) % 100000000

        if get_balance(buyer_id) < amount:
            await msg.reply("❌ Недостаточно средств.")
            return

        update_balance(buyer_id, -amount)
        cursor.execute("INSERT INTO deals (buyer_id, seller_id, amount, status) VALUES (?, ?, ?, 'hold')",
                       (buyer_id, seller_id, amount))
        conn.commit()
        await msg.reply("✅ Сделка создана. Когда подтвердите — средства переведутся продавцу. Напишите /confirm")

    except:
        await msg.reply("⚠ Ошибка в формате. Пример: sellerusername 10.5")

@dp.message_handler(commands=["confirm"])
async def confirm_deal(msg: types.Message):
    buyer_id = msg.from_user.id
    cursor.execute("SELECT id, seller_id, amount FROM deals WHERE buyer_id = ? AND status = 'hold'", (buyer_id,))
    deal = cursor.fetchone()

    if not deal:
        await msg.reply("❌ Нет активной сделки.")
        return

    deal_id, seller_id, amount = deal
    update_balance(seller_id, amount)
    cursor.execute("UPDATE deals SET status = 'completed' WHERE id = ?", (deal_id,))
    conn.commit()
    await msg.reply("✅ Сделка подтверждена, средства переведены продавцу.")

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    executor.start_polling(dp, skip_updates=True)

