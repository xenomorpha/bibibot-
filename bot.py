import asyncio
import os
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
    [KeyboardButton(text="📈 Прогресс"), KeyboardButton(text="📁 Проекты")],
    [KeyboardButton(text="🎯 За неделю")]
], resize_keyboard=True)

API_TOKEN = os.getenv("API_TOKEN")
bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
scheduler = AsyncIOScheduler()

# Кнопки под задачами
def get_task_buttons(task_id):
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Сделано", callback_data=f"done:{task_id}")
    builder.button(text="🔁 Напомнить позже", callback_data=f"later:{task_id}")
    builder.button(text="❌ Пропустить", callback_data=f"missed:{task_id}")
    return builder.as_markup()

@dp.message(F.text == "/start")
async def start_handler(message: Message):
    await database.create_user(message.from_user.id)
    await message.answer("Привет, я Биби 🌱 Я помогу тебе организовать свои дела и выполнять их во время. Какие у тебя есть задачи?", reply_markup=main_menu)

@dp.message(F.text.regexp(r"^.+ / \\d{2}:\\d{2}( / \\d{2}\\.\\d{2})?( / #.+)?$"))
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
        print("Ошибка сохранения:", e)
        await message.answer("Формат: Название / HH:MM / ДД.ММ / #проект (опционально)")

@dp.message(F.text.startswith("🌟 Добавить задачу"))
async def add_task_help(message: Message):
    await message.answer(
        "📝 Чтобы добавить задачу, напиши её вот так:\n\n"
        "<code>Прочитать книгу / 18:00</code>\n"
        "<code>Сьесть лягушку / 19:30 / 17.07</code>\n"
        "<code>Сходить в бассейн / 14:00 / 20.07 / #работа</code>\n\n"
        "⏰ Формат: <b>Название / Время / Дата / #проект</b> (дата и проект — по желанию)"
    )

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

@dp.message(F.text == "🎯 За неделю")
async def show_done_week(message: Message):
    tasks = await database.get_completed_tasks_last_week(message.from_user.id)
    if not tasks:
        await message.answer("На этой неделе пока ничего не выполнено 🌱")
        return
    text = "<b>Выполненные задачи за неделю:</b>\n\n"
    for title, ts in tasks:
        date_str = datetime.fromisoformat(ts).strftime("%d.%m %H:%M")
        text += f"✅ {title} ({date_str})\n"
    await message.answer(text)

# 📈 Прогресс
@dp.message(F.text == "📈 Прогресс")
async def show_progress(message: Message):
    stats = await database.get_user_stats(message.from_user.id)
    total = stats["done"] + stats["missed"]
    percent = int((stats["done"] / total) * 100) if total else 0
    await message.answer(f"""
<b>Твоя дисциплина 🌱</b>

✅ Выполнено задач: <b>{stats["done"]}</b>
❌ Пропущено: <b>{stats["missed"]}</b>
📊 Дисциплина: <b>{percent}%</b>

📅 Дней с выполнениями: <b>{stats["active_days"]}</b>
🔥 Подряд дней: <b>{stats["streak"]}</b>

Отличный результат! Продолжай в том же духе!
""")
    
# ✅ Обработка: задача выполнена
@dp.callback_query(F.data.startswith("done:"))
async def handle_done(callback: CallbackQuery):
    task_id = int(callback.data.split(":")[1])
    await database.mark_task_done(task_id)
    await callback.message.answer("Молодец! Задача отмечена как выполненная 💚")
    await callback.answer()

# ❌ Обработка: задача пропущена
@dp.callback_query(F.data.startswith("missed:"))
async def handle_missed(callback: CallbackQuery):
    task_id = int(callback.data.split(":")[1])
    await database.mark_task_missed(task_id)
    await callback.message.answer("Окей, двигаемся дальше. Главное — не останавливаться ☁️")
    await callback.answer()

# 🔁 Обработка: напомнить позже
@dp.callback_query(F.data.startswith("later:"))
async def handle_later(callback: CallbackQuery):
    task_id = int(callback.data.split(":")[1])
    builder = InlineKeyboardBuilder()
    for label, mins in [("15 мин", 15), ("30 мин", 30), ("1 час", 60)]:
        builder.button(text=label, callback_data=f"postpone:{task_id}:{mins}")
    await callback.message.answer("На сколько хочешь отложить? ⏳", reply_markup=builder.as_markup())
    await callback.answer()

# ⏰ Применить отложенную задачу
@dp.callback_query(F.data.startswith("postpone:"))
async def apply_postpone(callback: CallbackQuery):
    _, task_id, minutes = callback.data.split(":")
    new_time = await database.postpone_task(int(task_id), int(minutes))
    await callback.message.answer(f"Окей, напомню позже в {new_time} ⏰")
    await callback.answer()

# 📁 Список проектов с прогрессом
@dp.message(F.text == "📁 Проекты")
async def list_projects(message: Message):
    projects = await database.get_user_projects_with_progress(message.from_user.id)

    if not projects:
        await message.answer(
            "📁 Проекты — это группы задач.\n\n"
            "➕ Чтобы создать новый проект, нажми на кнопку или отправь сообщение:\n"
            "<code>проект: Название</code>\n\n"
            "📝 Чтобы добавить задачу в проект, просто укажи его хэштег:\n"
            "<code>Сделать презентацию / 10:00 / 18.07 / #работа</code>\n\n"
            "✅ Чтобы завершить проект, напиши:\n"
            "<code>завершить проект Название</code>"
            "🗑 Чтобы удалить проект напиши:\n"
            "<code>удалить проект Название</code>"

        )
        return

    # Отображаем список с прогрессом
    sorted_projects = sorted(
        projects,
        key=lambda x: (x[2] and x[3] and x[3] / x[2]) if x[2] else 0,
        reverse=True
    )

    builder = InlineKeyboardBuilder()
    for project_id, title, total, completed in sorted_projects:
        percent = int((completed / total) * 100) if total else 0
        builder.button(text=f"{title} ({percent}%)", callback_data=f"project:{project_id}")
    
    builder.button(text="➕ Новый проект", callback_data="new_project")

    await message.answer(
        "<b>📁 Твои проекты:</b>\nНажми на проект, чтобы посмотреть задачи ⬇️",
        reply_markup=builder.as_markup()
    )

@dp.callback_query(F.data.startswith("project:"))
async def show_project_tasks(callback: CallbackQuery):
    project_id = int(callback.data.split(":")[1])
    tasks = await database.get_tasks_for_project(project_id)

    if not tasks:
        await callback.message.answer("В этом проекте пока нет задач.")
    else:
        text = "<b>Задачи проекта:</b>\n\n"
        for title, time, date_str, completed in tasks:
            status = "✅" if completed else "🔲"
            text += f"{status} {title} — {date_str} {time}\n"

        await callback.message.answer(text)

    await callback.answer()


# ➕ Создание проекта (кнопкой)
@dp.callback_query(F.data == "new_project")
async def new_project_prompt(callback: CallbackQuery):
    await callback.message.answer("Напиши название нового проекта:\n<code>проект: Название</code>")
    await callback.answer()

# ➕ Создание проекта (текстом)
@dp.message(F.text.regexp(r"^проект: .+"))
async def create_project_from_text(message: Message):
    title = message.text.replace("проект: ", "").strip()
    await database.create_project(message.from_user.id, title)
    await message.answer(f"Проект «{title}» создан! Чтобы добавить задачи — используй / HH:MM / ДД.ММ / #название_проекта")

# ✅ Завершить проект
@dp.message(F.text.startswith("завершить проект "))
async def handle_complete_project(message: Message):
    title = message.text.replace("завершить проект ", "").strip()
    project_id = await database.get_project_id(message.from_user.id, title)
    if project_id:
        await database.complete_project(project_id)
        await message.answer(f"✅ Все задачи проекта «{title}» помечены как выполненные.")
    else:
        await message.answer("⚠️ Проект не найден.")

@dp.message(F.text.startswith("удалить проект "))
async def delete_project_handler(message: Message):
    title = message.text.replace("удалить проект ", "").strip()
    project_id = await database.get_project_id(message.from_user.id, title)
    if project_id:
        await database.delete_project(project_id)
        await message.answer(f"🗑 Проект «{title}» и все его задачи удалены.")
    else:
        await message.answer("⚠️ Проект не найден.")

@dp.message(F.text == "/help")
async def help_command(message: Message):
    await message.answer("""
🛠 <b>Команды и пояснения</b>

🌟 <b>Добавить задачу</b>
Формат: Название / ЧЧ:ММ / ДД.ММ / #проект (по желанию)

📋 <b>Мои задачи</b>
Список задач на сегодня

🏋️ <b>Выполненные</b>
Список завершённых задач

📈 <b>Прогресс</b>
Показывает твой процент выполнения и дисциплину

📁 <b>Проекты</b>
Управление проектами и группами задач

Например: Убраться / 21:00 / 18.07 / #дом
""")

async def send_reminders():
    tasks = await database.get_tasks_for_now()
    for user_id, task_id, title in tasks:
        await bot.send_message(user_id, f"🌸 Напоминание: {title}", reply_markup=get_task_buttons(task_id))

async def notify_all_users():
    users = await database.get_all_user_ids()

    print(f"🙋 Найдено пользователей: {len(users)}")  

    for user_id in users:
        try:
            await bot.send_message(
                user_id,
                "✨ Бот обновился! Теперь он работает 24/7 на сервере! Чтобы пользоваться новой версией и всегда быть на связи — нажмите /start"
            )
        except Exception as e:
            print(f"❌ Не удалось отправить сообщение {user_id}: {e}")


# 🚀 основной запуск
async def main():
    await database.init()
    await notify_all_users()  
    scheduler.add_job(send_reminders, "interval", minutes=1)
    scheduler.start()
    print("✨ Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())





