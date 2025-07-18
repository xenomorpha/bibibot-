import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.types import Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.client.default import DefaultBotProperties
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime
import database
import aiosqlite

# 🌿 Главное меню
main_menu = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text="🌟 Добавить задачу")],
    [KeyboardButton(text="📋 Мои задачи"), KeyboardButton(text="🏁 Выполненные")],
    [KeyboardButton(text="📈 Прогресс")]
], resize_keyboard=True)

API_TOKEN = '7828773245:AAHa5Qlzbn6FeByak40UA6liCpLzwSMlqOk'

bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
scheduler = AsyncIOScheduler()

# 🎯 Кнопки под задачами
def get_task_buttons(task_id):
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Сделано", callback_data=f"done:{task_id}")
    builder.button(text="🔁 Напомнить позже", callback_data=f"later:{task_id}")
    builder.button(text="🚫 Пропустить", callback_data=f"missed:{task_id}")
    return builder.as_markup()

# 🛎 Старт
@dp.message(F.text == "/start")
async def start_handler(message: Message):
    await database.create_user(message.from_user.id)
    await message.answer("Привет, я Биби 🌱 Я помогу тебе организовать свои дела и выполнять их во время. Какие у тебя есть задачи?", reply_markup=main_menu)

# ✍️ Добавление задачи
@dp.message(F.text.regexp(r"^.+ / \d{2}:\d{2}( / \d{2}\.\d{2})?$"))
async def save_task(message: Message):
    try:
        parts = [p.strip() for p in message.text.split("/") if p.strip()]
        title = parts[0]
        time_str = parts[1]
        task_time = datetime.strptime(time_str, "%H:%M").time()

        # Если есть дата
        if len(parts) == 3:
            date_str = parts[2]
            parsed_date = datetime.strptime(date_str, "%d.%m")
            task_date = parsed_date.replace(year=datetime.now().year).date()
        else:
            task_date = datetime.now().date()

        if "#" in parts[-1]:
    project_part = parts[-1]
    parts = parts[:-1]
    project_name = project_part.replace("#", "").strip()
    project_id = await database.get_project_id(message.from_user.id, project_name)
else:
    project_id = None
    

        await database.add_task(message.from_user.id, title, task_time, task_date)

await database.add_task(message.from_user.id, title, task_time, task_date, project_id)

        await message.answer(f"📝 Задача «{title}» добавлена на {task_date.strftime('%d.%m')} в {task_time.strftime('%H:%M')}")
    except Exception as e:
        print("Ошибка сохранения задачи:", e)

    
        await message.answer("Формат: Название / HH:MM или Название / HH:MM / DD.MM")

# 👇 Добавить задачку по кнопке
@dp.message(F.text == "🌟 Добавить задачу")
async def add_prompt(message: Message):
    await message.answer("Напиши задачу в формате:\n<название> / HH:MM или\n<название> / HH:MM / ДД.ММ 🌸")

# 📅 Список задач на сегодня
@dp.message(F.text == "📋 Мои задачи")
async def show_today_tasks(message: Message):
    tasks = await database.get_tasks_for_user_today(message.from_user.id)
    if not tasks:
        await message.answer("Сегодня всё свободно. Можно отдохнуть или сделать что-то по душе 🌼")
        return

    text = "<b>Твои задачи на сегодня:</b>\n\n"
    for title, task_time in tasks:
        text += f"🕒 <b>{task_time}</b> — {title}\n"

    await message.answer(text)

# ✅ Выполненные задачи
@dp.message(F.text == "🏁 Выполненные")
async def show_done(message: Message):
    tasks = await database.get_completed_tasks(message.from_user.id)
    if not tasks:
        await message.answer("Пока ничего не выполнено. Но это только начало 💪")
        return

    text = "<b>Вот, что ты уже сделала:</b>\n\n"
    for title, ts in tasks[:10]:
        date_str = datetime.fromisoformat(ts).strftime("%d.%m %H:%M")
        text += f"✅ {title} ({date_str})\n"

    await message.answer(text)



 @dp.message(F.text.startswith("завершить проект "))
async def handle_complete_project(message: Message):
    title = message.text.replace("завершить проект ", "").strip()
    project_id = await database.get_project_id(message.from_user.id, title)
    if project_id:
        await database.complete_project(project_id)
        await message.answer(f"✅ Все задачи проекта «{title}» помечены как выполненные.")
    else:
        await message.answer("⚠️ Проект не найден.")


# 📈 Прогресс (заглушка)
@dp.message(F.text == "📈 Прогресс")
async def show_progress(message: Message):
    stats = await database.get_user_stats(message.from_user.id)
    total = stats["done"] + stats["missed"]
    percent = int((stats["done"] / total) * 100) if total else 0

    await message.answer(f"""
<b>Твоя дисциплина 🌱</b>

✅ Выполнено задач: <b>{stats["done"]}</b>
🚫 Пропущено: <b>{stats["missed"]}</b>
📊 Дисциплина: <b>{percent}%</b>

📅 Дней с выполнениями: <b>{stats["active_days"]}</b>
🔥 Подряд дней: <b>{stats["streak"]}</b>

Ты умничка! Продолжай в том же духе!
""")

@dp.message(F.text.startswith("+проект "))
async def handle_add_project(message: Message):
    title = message.text[8:].strip()
    await database.create_project(message.from_user.id, title)
    await message.answer(f"📁 Проект «{title}» создан! Теперь добавь задачи к нему.")


# ✅ Обработка: выполнено
@dp.callback_query(F.data.startswith("done:"))
async def handle_done(callback: CallbackQuery):
    print("✅ Хендлер нажатия 'Сделано' сработал")
    task_id = int(callback.data.split(":")[1])
    await database.mark_task_done(task_id)
    await callback.message.answer("Молодец! Задача отмечена как выполненная 💚")
    await callback.answer()

# ❌ Обработка: пропущено
@dp.callback_query(F.data.startswith("missed:"))
async def handle_missed(callback: CallbackQuery):
    task_id = int(callback.data.split(":")[1])
    await database.mark_task_missed(task_id)
    await callback.message.answer("Окей, двигаемся дальше. Главное — не останавливаться ☁️")
    await callback.answer()

# 🔁 Отложить задачу
@dp.callback_query(F.data.startswith("later:"))
async def handle_later(callback: CallbackQuery):
    task_id = int(callback.data.split(":")[1])
    builder = InlineKeyboardBuilder()
    for label, mins in [("15 мин", 15), ("30 мин", 30), ("1 час", 60)]:
        builder.button(text=label, callback_data=f"postpone:{task_id}:{mins}")
    await callback.message.answer("На сколько хочешь отложить? ⏳", reply_markup=builder.as_markup())
    await callback.answer()

@dp.callback_query(F.data.startswith("postpone:"))
async def apply_postpone(callback: CallbackQuery):
    _, task_id, minutes = callback.data.split(":")
    new_time = await database.postpone_task(int(task_id), int(minutes))
    await callback.message.answer(f"Окей, напомню позже в {new_time} ⏰")
    await callback.answer()

# 🔔 Напоминания
async def send_reminders():
    tasks = await database.get_tasks_for_now()
    for user_id, task_id, title in tasks:
        await bot.send_message(
            user_id,
            f"🌸 Напоминание: {title}",
            reply_markup=get_task_buttons(task_id)
        )


async def migrate_add_columns():
    async with aiosqlite.connect("tasks.db") as db:
        try:
            await db.execute("ALTER TABLE tasks ADD COLUMN completed INTEGER DEFAULT 0")
        except:
            print("⚠️ Колонка 'completed' уже есть")
        try:
            await db.execute("ALTER TABLE tasks ADD COLUMN completed_at TEXT")
        except:
            print("⚠️ Колонка 'completed_at' уже есть")
        try:
            await db.execute("ALTER TABLE tasks ADD COLUMN missed INTEGER DEFAULT 0")
        except:
            print("⚠️ Колонка 'missed' уже есть")
        await db.commit()

# Запуск
async def main():
    await database.init()
    #await migrate_add_columns()  
    scheduler.add_job(send_reminders, "interval", minutes=1)
    scheduler.start()
    print("✨ Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
