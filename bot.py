import os
import asyncio
from datetime import datetime
from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.types import Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.client.default import DefaultBotProperties
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import database
import aiosqlite

# Главное меню
main_menu = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text="🌟 Добавить задачу")],
    [KeyboardButton(text="📋 Мои задачи"), KeyboardButton(text="🏁 Выполненные")],
    [KeyboardButton(text="📈 Прогресс"), KeyboardButton(text="📁 Проекты")]
], resize_keyboard=True)

# Кнопки под задачами
def get_task_buttons(task_id):
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Сделано", callback_data=f"done:{task_id}")
    builder.button(text="🔁 Напомнить позже", callback_data=f"later:{task_id}")
    builder.button(text="❌ Пропустить", callback_data=f"missed:{task_id}")
    return builder.as_markup()

# Напоминания
async def send_reminders(bot: Bot):
    tasks = await database.get_tasks_for_now()
    for user_id, task_id, title in tasks:
        await bot.send_message(
            user_id,
            f"🌸 Напоминание: {title}",
            reply_markup=get_task_buttons(task_id)
        )

async def main():
    API_TOKEN = os.getenv("API_TOKEN")
    if not API_TOKEN:
        raise RuntimeError("❌ API_TOKEN is not set! Please add it in Railway → Settings → Variables")

    bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()

    await database.init()

    # Команды
    @dp.message(F.text == "/start")
    async def start_handler(message: Message):
        await database.create_user(message.from_user.id)
        await message.answer("Привет, я Биби 🌱 Я помогу тебе организовать свои дела и выполнять их во время. Какие у тебя есть задачи?", reply_markup=main_menu)

    @dp.message(F.text == "/help")
    async def help_command(message: Message):
        await message.answer("""
🛠 <b>Команды и пояснения</b>

🌟 <b>Добавить задачу</b>
Формат: Название / ЧЧ:ММ / ДД.ММ / #проект (по желанию)

📋 <b>Мои задачи</b> — список задач на сегодня  
🏁 <b>Выполненные</b> — завершённые задачи  
📈 <b>Прогресс</b> — процент выполнения  
📁 <b>Проекты</b> — управление проектами
""")

    # Кнопки (обычные)
    @dp.message(F.text == "🌟 Добавить задачу")
    async def show_add_help(message: Message):
        await message.answer("✍️ Чтобы добавить задачу, напиши:\n\nНазвание / ЧЧ:ММ / ДД.ММ / #проект")

    @dp.message(F.text == "📋 Мои задачи")
    async def show_tasks(message: Message):
        tasks = await database.get_tasks_for_today(message.from_user.id)
        if not tasks:
            await message.answer("😌 У тебя пока нет задач на сегодня.")
            return
        for task_id, title, time in tasks:
            await message.answer(f"🕒 {time} — {title}", reply_markup=get_task_buttons(task_id))

    @dp.message(F.text == "🏁 Выполненные")
    async def show_done_tasks(message: Message):
        tasks = await database.get_done_tasks(message.from_user.id)
        if not tasks:
            await message.answer("📭 У тебя пока нет выполненных задач.")
            return
        msg = "\n".join([f"✅ {title} ({time})" for title, time in tasks])
        await message.answer(f"<b>🏁 Выполненные задачи:</b>\n\n{msg}")

    @dp.message(F.text == "📈 Прогресс")
    async def show_progress(message: Message):
        percent = await database.get_progress(message.from_user.id)
        await message.answer(f"📊 Ты выполнил {percent}% задач!")

    @dp.message(F.text == "📁 Проекты")
    async def show_projects(message: Message):
        projects = await database.get_projects(message.from_user.id)
        if not projects:
            await message.answer("🗂 У тебя пока нет проектов. Добавь #название при создании задачи.")
            return
        msg = "\n".join([f"📁 {name}" for name in projects])
        await message.answer(f"<b>📁 Твои проекты:</b>\n\n{msg}")

    # Добавление задачи
    @dp.message(F.text.regexp(r"^.+ / \d{2}:\d{2}( / \d{2}\.\d{2})?( / #.+)?$"))
    async def save_task(message: Message):
        try:
            parts = [p.strip() for p in message.text.split("/") if p.strip()]
            title = parts[0]
            time_str = parts[1]
            task_time = datetime.strptime(time_str, "%H:%M").time()
            task_date = datetime.now().date()
            project_id = None

            for p in parts[2:]:
                if p.startswith("#"):
                    project_name = p.replace("#", "").strip()
                    project_id = await database.get_project_id(message.from_user.id, project_name)
                elif "." in p:
                    task_date = datetime.strptime(p, "%d.%m").replace(year=datetime.now().year).date()

            await database.add_task(message.from_user.id, title, task_time, task_date, project_id)

            msg = f"📝 Задача «{title}» добавлена на {task_date.strftime('%d.%m')} в {task_time.strftime('%H:%M')}"
            if project_id:
                msg += f" в проект «{project_name}»"

            await message.answer(msg)

        except Exception as e:
            print("❌ Ошибка сохранения задачи:", e)
            await message.answer("Формат: Название / HH:MM / ДД.ММ / #проект (опционально)")

    # Inline-кнопки
    @dp.callback_query(F.data.startswith("done:"))
    async def handle_done(call: CallbackQuery):
        task_id = int(call.data.split(":")[1])
        await database.mark_task_done(task_id)
        await call.message.edit_text("✅ Задача отмечена как выполненная!")

    @dp.callback_query(F.data.startswith("later:"))
    async def handle_later(call: CallbackQuery):
        await call.answer("⏰ Напомню позже!", show_alert=False)

    @dp.callback_query(F.data.startswith("missed:"))
    async def handle_missed(call: CallbackQuery):
        await call.message.edit_text("🚫 Задача пропущена.")

    # Планировщик
    scheduler = AsyncIOScheduler()
    scheduler.add_job(send_reminders, "interval", minutes=1, args=[bot])
    scheduler.start()

    print("✅ Бот запущен и слушает события")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())



