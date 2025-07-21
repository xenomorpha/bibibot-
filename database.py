import asyncpg
from datetime import datetime, date, timedelta
import os

DATABASE_URL = os.getenv("DATABASE_URL")


async def connect():
    return await asyncpg.connect(DATABASE_URL)


async def init():
    conn = await connect()
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY
        );
        CREATE TABLE IF NOT EXISTS tasks (
            id SERIAL PRIMARY KEY,
            user_id BIGINT,
            title TEXT,
            time TEXT,
            date TEXT,
            completed INTEGER DEFAULT 0,
            completed_at TEXT,
            missed INTEGER DEFAULT 0,
            project_id INTEGER
        );
        CREATE TABLE IF NOT EXISTS task_logs (
            id SERIAL PRIMARY KEY,
            user_id BIGINT,
            task_id INTEGER,
            action TEXT,
            timestamp TEXT
        );
        CREATE TABLE IF NOT EXISTS projects (
            id SERIAL PRIMARY KEY,
            user_id BIGINT,
            title TEXT
        );
    """)
    await conn.close()


async def create_user(user_id: int):
    conn = await connect()
    await conn.execute("INSERT INTO users (user_id) VALUES ($1) ON CONFLICT DO NOTHING", user_id)
    await conn.close()


async def add_task(user_id: int, title: str, time: object, task_date: date, project_id: int = None):
    conn = await connect()
    await conn.execute("""
        INSERT INTO tasks (user_id, title, time, date, project_id)
        VALUES ($1, $2, $3, $4, $5)
    """, user_id, title, time.strftime("%H:%M"), task_date.strftime("%Y-%m-%d"), project_id)
    await conn.close()


async def get_tasks_for_now():
    now = datetime.now()
    current_time = now.strftime("%H:%M")
    current_date = now.strftime("%Y-%m-%d")
    conn = await connect()
    rows = await conn.fetch("""
        SELECT user_id, id, title FROM tasks
        WHERE time = $1 AND date = $2 AND completed = 0 AND missed = 0
    """, current_time, current_date)
    await conn.close()
    return rows


async def get_tasks_for_user_today(user_id: int):
    today = date.today().strftime("%Y-%m-%d")
    conn = await connect()
    rows = await conn.fetch("""
        SELECT title, time FROM tasks
        WHERE user_id = $1 AND date = $2 AND completed = 0 AND missed = 0
        ORDER BY time ASC
    """, user_id, today)
    await conn.close()
    return rows


async def get_completed_tasks(user_id: int):
    conn = await connect()
    rows = await conn.fetch("""
        SELECT tasks.title, task_logs.timestamp
        FROM task_logs
        JOIN tasks ON task_logs.task_id = tasks.id
        WHERE task_logs.user_id = $1 AND task_logs.action = 'done'
        ORDER BY task_logs.timestamp DESC
    """, user_id)
    await conn.close()
    return rows


async def mark_task_done(task_id: int):
    conn = await connect()
    row = await conn.fetchrow("SELECT user_id FROM tasks WHERE id = $1", task_id)
    if row:
        user_id = row['user_id']
        await conn.execute("""
            UPDATE tasks SET completed = 1, completed_at = CURRENT_TIMESTAMP WHERE id = $1
        """, task_id)
        await conn.execute("""
            INSERT INTO task_logs (user_id, task_id, action, timestamp)
            VALUES ($1, $2, 'done', CURRENT_TIMESTAMP)
        """, user_id, task_id)
    await conn.close()


async def mark_task_missed(task_id: int):
    conn = await connect()
    row = await conn.fetchrow("SELECT user_id FROM tasks WHERE id = $1", task_id)
    if row:
        user_id = row['user_id']
        await conn.execute("UPDATE tasks SET missed = 1 WHERE id = $1", task_id)
        await conn.execute("""
            INSERT INTO task_logs (user_id, task_id, action, timestamp)
            VALUES ($1, $2, 'missed', CURRENT_TIMESTAMP)
        """, user_id, task_id)
    await conn.close()


async def postpone_task(task_id: int, minutes: int):
    new_time = (datetime.now() + timedelta(minutes=minutes)).strftime("%H:%M")
    conn = await connect()
    await conn.execute("UPDATE tasks SET time = $1 WHERE id = $2", new_time, task_id)
    await conn.close()
    return new_time


async def log_task_action(user_id: int, task_id: int, action: str):
    timestamp = datetime.now().isoformat()
    conn = await connect()
    await conn.execute("""
        INSERT INTO task_logs (user_id, task_id, action, timestamp)
        VALUES ($1, $2, $3, $4)
    """, user_id, task_id, action, timestamp)
    await conn.close()


async def get_user_stats(user_id: int):
    conn = await connect()

    done = await conn.fetchval("""
        SELECT COUNT(*) FROM task_logs WHERE user_id = $1 AND action = 'done'
    """, user_id)

    missed = await conn.fetchval("""
        SELECT COUNT(*) FROM task_logs WHERE user_id = $1 AND action = 'missed'
    """, user_id)

    rows = await conn.fetch("""
        SELECT DISTINCT DATE(timestamp)
        FROM task_logs
        WHERE user_id = $1 AND action = 'done'
        ORDER BY DATE(timestamp)
    """, user_id)

    await conn.close()

    days = [datetime.strptime(str(row['date']), "%Y-%m-%d").date() for row in rows]

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


async def create_project(user_id: int, title: str):
    conn = await connect()
    await conn.execute("INSERT INTO projects (user_id, title) VALUES ($1, $2)", user_id, title)
    await conn.close()


async def get_project_id(user_id: int, title: str):
    conn = await connect()
    row = await conn.fetchrow("SELECT id FROM projects WHERE user_id = $1 AND title = $2", user_id, title)
    await conn.close()
    return row['id'] if row else None


async def complete_project(project_id: int):
    conn = await connect()
    await conn.execute("""
        UPDATE tasks SET completed = 1, completed_at = CURRENT_TIMESTAMP
        WHERE project_id = $1
    """, project_id)
    await conn.close()


async def get_user_projects(user_id: int):
    conn = await connect()
    rows = await conn.fetch("SELECT id, title FROM projects WHERE user_id = $1", user_id)
    await conn.close()
    return rows


async def get_tasks_for_project(project_id: int):
    conn = await connect()
    rows = await conn.fetch("""
        SELECT title, time, date, completed
        FROM tasks
        WHERE project_id = $1
        ORDER BY date, time
    """, project_id)
    await conn.close()
    return rows


async def get_user_projects_with_progress(user_id: int):
    conn = await connect()
    rows = await conn.fetch("""
        SELECT p.id, p.title,
               COUNT(t.id) AS total,
               SUM(CASE WHEN t.completed = 1 THEN 1 ELSE 0 END) AS completed
        FROM projects p
        LEFT JOIN tasks t ON t.project_id = p.id
        WHERE p.user_id = $1
        GROUP BY p.id
    """, user_id)
    await conn.close()
    return rows


async def delete_project(project_id: int):
    conn = await connect()
    await conn.execute("DELETE FROM tasks WHERE project_id = $1", project_id)
    await conn.execute("DELETE FROM projects WHERE id = $1", project_id)
    await conn.close()


async def get_completed_tasks_last_week(user_id: int):
    one_week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    conn = await connect()
    rows = await conn.fetch("""
        SELECT tasks.title, task_logs.timestamp
        FROM task_logs
        JOIN tasks ON task_logs.task_id = tasks.id
        WHERE task_logs.user_id = $1 AND task_logs.action = 'done'
        AND DATE(task_logs.timestamp) >= $2
        ORDER BY task_logs.timestamp DESC
    """, user_id, one_week_ago)
    await conn.close()
    return rows


async def get_all_user_ids():
    conn = await connect()
    rows = await conn.fetch("SELECT user_id FROM users")
    await conn.close()
    return [row['user_id'] for row in rows]

