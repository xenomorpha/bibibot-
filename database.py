import aiosqlite
from datetime import datetime, date, timedelta

DB_NAME = "tasks.db"

# ✅ Инициализация базы данных
async def init():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                title TEXT,
                time TEXT,
                date TEXT,
                completed INTEGER DEFAULT 0,
                completed_at TEXT,
                missed INTEGER DEFAULT 0,
                project_id INTEGER
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS task_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                task_id INTEGER,
                action TEXT,
                timestamp TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                title TEXT
            )
        """)
        await db.commit()

# ✅ Создание пользователя
async def create_user(user_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
        await db.commit()

# ✅ Добавление задачи
async def add_task(user_id: int, title: str, time: object, task_date: date, project_id: int = None):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            INSERT INTO tasks (user_id, title, time, date, project_id)
            VALUES (?, ?, ?, ?, ?)
        """, (
            user_id,
            title,
            time.strftime("%H:%M"),
            task_date.strftime("%Y-%m-%d"),
            project_id
        ))
        await db.commit()

# ✅ Задачи на сейчас
async def get_tasks_for_now():
    now = datetime.now()
    current_time = now.strftime("%H:%M")
    current_date = now.strftime("%Y-%m-%d")
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("""
            SELECT user_id, id, title FROM tasks
            WHERE time = ? AND date = ? AND completed = 0 AND missed = 0
        """, (current_time, current_date))
        return await cursor.fetchall()

# ✅ Задачи на сегодня
async def get_tasks_for_user_today(user_id: int):
    today = date.today().strftime("%Y-%m-%d")
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("""
            SELECT title, time FROM tasks
            WHERE user_id = ? AND date = ? AND completed = 0 AND missed = 0
            ORDER BY time ASC
        """, (user_id, today))
        return await cursor.fetchall()

# ✅ Выполненные задачи
tasks = await database.get_completed_tasks(message.from_user.id)
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("""
            SELECT tasks.title, task_logs.timestamp
            FROM task_logs
            JOIN tasks ON task_logs.task_id = tasks.id
            WHERE task_logs.user_id = ? AND task_logs.action = 'done'
            ORDER BY task_logs.timestamp DESC
        """, (user_id,))
        return await cursor.fetchall()

# ✅ Отметить задачу как выполненную
async def mark_task_done(task_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT user_id FROM tasks WHERE id = ?", (task_id,))
        row = await cursor.fetchone()
        if row:
            user_id = row[0]
            await db.execute("""
                UPDATE tasks SET completed = 1, completed_at = CURRENT_TIMESTAMP WHERE id = ?
            """, (task_id,))
            await db.execute("""
                INSERT INTO task_logs (user_id, task_id, action, timestamp)
                VALUES (?, ?, 'done', CURRENT_TIMESTAMP)
            """, (user_id, task_id))
            await db.commit()

# ✅ Отметить задачу как пропущенную
async def mark_task_missed(task_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT user_id FROM tasks WHERE id = ?", (task_id,))
        row = await cursor.fetchone()
        if row:
            user_id = row[0]
            await db.execute("UPDATE tasks SET missed = 1 WHERE id = ?", (task_id,))
            await db.execute("""
                INSERT INTO task_logs (user_id, task_id, action, timestamp)
                VALUES (?, ?, 'missed', CURRENT_TIMESTAMP)
            """, (user_id, task_id))
            await db.commit()


# ✅ Перенести задачу
async def postpone_task(task_id: int, minutes: int):
    new_time = (datetime.now() + timedelta(minutes=minutes)).strftime("%H:%M")
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE tasks SET time = ? WHERE id = ?", (new_time, task_id))
        await db.commit()
    return new_time

# ✅ Лог вручную
async def log_task_action(user_id: int, task_id: int, action: str):
    timestamp = datetime.now().isoformat()
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            INSERT INTO task_logs (user_id, task_id, action, timestamp)
            VALUES (?, ?, ?, ?)
        """, (user_id, task_id, action, timestamp))
        await db.commit()

# 📊 Прогресс
async def get_user_stats(user_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        # done
        cursor = await db.execute("""
            SELECT COUNT(*) FROM task_logs WHERE user_id = ? AND action = 'done'
        """, (user_id,))
        done = (await cursor.fetchone())[0]

        # missed
        cursor = await db.execute("""
            SELECT COUNT(*) FROM task_logs WHERE user_id = ? AND action = 'missed'
        """, (user_id,))
        missed = (await cursor.fetchone())[0]

        # streak
        cursor = await db.execute("""
            SELECT DISTINCT DATE(timestamp)
            FROM task_logs
            WHERE user_id = ? AND action = 'done'
            ORDER BY DATE(timestamp)
        """, (user_id,))
        days = [datetime.strptime(row[0], "%Y-%m-%d").date() for row in await cursor.fetchall()]

        streak = 0
        today = date.today()
        for i in range(len(days) - 1, -1, -1):
            if days[i] == today - timedelta(days=streak):
                streak += 1
            else:
                break

        return {
            "done": done,
            "missed": missed,
            "active_days": len(days),
            "streak": streak
        }

# ➕ Проект
async def create_project(user_id: int, title: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT INTO projects (user_id, title) VALUES (?, ?)", (user_id, title))
        await db.commit()

# 🔍 Найти проект
async def get_project_id(user_id: int, title: str):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("""
            SELECT id FROM projects WHERE user_id = ? AND title = ?
        """, (user_id, title))
        row = await cursor.fetchone()
        return row[0] if row else None

# ✅ Завершить проект
async def complete_project(project_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            UPDATE tasks SET completed = 1, completed_at = CURRENT_TIMESTAMP
            WHERE project_id = ?
        """, (project_id,))
        await db.commit()

# 📁 Получить проекты пользователя
async def get_user_projects(user_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT id, title FROM projects WHERE user_id = ?", (user_id,))
        return await cursor.fetchall()

# 📋 Задачи проекта
async def get_tasks_for_project(project_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("""
            SELECT title, time, date, completed
            FROM tasks
            WHERE project_id = ?
            ORDER BY date, time
        """, (project_id,))
        return await cursor.fetchall()

# 📈 Прогресс проектов
async def get_user_projects_with_progress(user_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("""
            SELECT p.id, p.title,
                   COUNT(t.id) AS total,
                   SUM(CASE WHEN t.completed = 1 THEN 1 ELSE 0 END) AS completed
            FROM projects p
            LEFT JOIN tasks t ON t.project_id = p.id
            WHERE p.user_id = ?
            GROUP BY p.id
        """, (user_id,))
        return await cursor.fetchall()


