Database · PY
Copy

1import asyncpg
2from datetime import datetime, date, timedelta
3import os
4import ssl
5
6_pool = None
7
8DATABASE_URL = os.getenv("DATABASE_URL")
9if not DATABASE_URL:
10    raise RuntimeError("❌ DATABASE_URL не установлен!")
11
12async def connect():
13    global _pool
14    if _pool is None:
15        # Создаем SSL контекст для Railway/Render
16        ssl_context = ssl.create_default_context()
17        ssl_context.check_hostname = False
18        ssl_context.verify_mode = ssl.CERT_NONE
19        
20        _pool = await asyncpg.create_pool(
21            DATABASE_URL,
22            ssl=ssl_context,  # Изменено с ssl=False на ssl=ssl_context
23            timeout=60,
24            command_timeout=60,
25            min_size=1,
26            max_size=10
27        )
28    return _pool
29
30
31async def init():
32    pool = await connect()
33    async with pool.acquire() as conn:
34        await conn.execute("""
35            CREATE TABLE IF NOT EXISTS users (
36                user_id BIGINT PRIMARY KEY
37            );
38            CREATE TABLE IF NOT EXISTS tasks (
39                id SERIAL PRIMARY KEY,
40                user_id BIGINT,
41                title TEXT,
42                time TIME,
43                date DATE,
44                completed INTEGER DEFAULT 0,
45                completed_at TIMESTAMP,
46                missed INTEGER DEFAULT 0,
47                project_id INTEGER
48            );
49            CREATE TABLE IF NOT EXISTS task_logs (
50                id SERIAL PRIMARY KEY,
51                user_id BIGINT,
52                task_id INTEGER,
53                action TEXT,
54                timestamp TIMESTAMP
55            );
56            CREATE TABLE IF NOT EXISTS projects (
57                id SERIAL PRIMARY KEY,
58                user_id BIGINT,
59                title TEXT
60            );
61        """)
62
63async def create_user(user_id: int):
64    pool = await connect()
65    async with pool.acquire() as conn:
66        await conn.execute("INSERT INTO users (user_id) VALUES ($1) ON CONFLICT DO NOTHING", user_id)
67
68async def add_task(user_id: int, title: str, time: object, task_date: date, project_id: int = None):
69    pool = await connect()
70    async with pool.acquire() as conn:
71        await conn.execute("""
72            INSERT INTO tasks (user_id, title, time, date, project_id)
73            VALUES ($1, $2, $3, $4, $5)
74        """, user_id, title, time, task_date, project_id)
75
76
77async def get_tasks_for_now():
78    now = datetime.now()
79    current_time = now.strftime("%H:%M")  # 🔧 Преобразуем во ВРЕМЯ в строковом виде
80    current_date = now.strftime("%Y-%m-%d")  # 🔧 Преобразуем дату в строку
81    pool = await connect()
82    async with pool.acquire() as conn:
83        return await conn.fetch("""
84            SELECT user_id, id, title FROM tasks
85            WHERE to_char(time::time, 'HH24:MI') = $1 AND to_char(date::date, 'YYYY-MM-DD') = $2
86                  AND completed = 0 AND missed = 0
87        """, current_time, current_date)
88
89
90async def get_tasks_for_user_today(user_id: int):
91    today = date.today().strftime("%Y-%m-%d")  # 🔧 Преобразуем дату в строку
92    pool = await connect()
93    async with pool.acquire() as conn:
94        return await conn.fetch("""
95            SELECT title, time FROM tasks
96            WHERE user_id = $1 AND date::text = $2 AND completed = 0 AND missed = 0
97            ORDER BY time ASC
98        """, user_id, today)
99
100
101async def mark_task_done(task_id: int):
102    pool = await connect()
103    async with pool.acquire() as conn:
104        row = await conn.fetchrow("SELECT user_id FROM tasks WHERE id = $1", task_id)
105        if row:
106            user_id = row['user_id']
107            await conn.execute("""
108                UPDATE tasks SET completed = 1, completed_at = CURRENT_TIMESTAMP WHERE id = $1
109            """, task_id)
110            await conn.execute("""
111                INSERT INTO task_logs (user_id, task_id, action, timestamp)
112                VALUES ($1, $2, 'done', CURRENT_TIMESTAMP)
113            """, user_id, task_id)
114
115async def mark_task_missed(task_id: int):
116    pool = await connect()
117    async with pool.acquire() as conn:
118        row = await conn.fetchrow("SELECT user_id FROM tasks WHERE id = $1", task_id)
119        if row:
120            user_id = row['user_id']
121            await conn.execute("UPDATE tasks SET missed = 1 WHERE id = $1", task_id)
122            await conn.execute("""
123                INSERT INTO task_logs (user_id, task_id, action, timestamp)
124                VALUES ($1, $2, 'missed', CURRENT_TIMESTAMP)
125            """, user_id, task_id)
126
127async def postpone_task(task_id: int, minutes: int):
128    new_time = (datetime.now() + timedelta(minutes=minutes)).strftime("%H:%M")
129    pool = await connect()
130    async with pool.acquire() as conn:
131        await conn.execute("UPDATE tasks SET time = $1 WHERE id = $2", new_time, task_id)
132    return new_time
133
134async def log_task_action(user_id: int, task_id: int, action: str):
135    timestamp = datetime.now().isoformat()
136    pool = await connect()
137    async with pool.acquire() as conn:
138        await conn.execute("""
139            INSERT INTO task_logs (user_id, task_id, action, timestamp)
140            VALUES ($1, $2, $3, $4)
141        """, user_id, task_id, action, timestamp)
142
143async def get_user_stats(user_id: int):
144    pool = await connect()
145    async with pool.acquire() as conn:
146        done = await conn.fetchval("""
147            SELECT COUNT(*) FROM task_logs WHERE user_id = $1 AND action = 'done'
148        """, user_id)
149        missed = await conn.fetchval("""
150            SELECT COUNT(*) FROM task_logs WHERE user_id = $1 AND action = 'missed'
151        """, user_id)
152        rows = await conn.fetch("""
153            SELECT DISTINCT DATE(timestamp)
154            FROM task_logs
155            WHERE user_id = $1 AND action = 'done'
156            ORDER BY DATE(timestamp)
157        """, user_id)
158
159    days = [datetime.strptime(str(row['date']), "%Y-%m-%d").date() for row in rows]
160    streak = 0
161    today = date.today()
162    for i in range(len(days) - 1, -1, -1):
163        if days[i] == today - timedelta(days=streak):
164            streak += 1
165        else:
166            break
167
168    return {
169        "done": done,
170        "missed": missed,
171        "active_days": len(days),
172        "streak": streak
173    }
174
175async def create_project(user_id: int, title: str):
176    pool = await connect()
177    async with pool.acquire() as conn:
178        await conn.execute("INSERT INTO projects (user_id, title) VALUES ($1, $2)", user_id, title)
179
180async def get_project_id(user_id: int, title: str):
181    pool = await connect()
182    async with pool.acquire() as conn:
183        row = await conn.fetchrow("SELECT id FROM projects WHERE user_id = $1 AND title = $2", user_id, title)
184        return row['id'] if row else None
185
186async def complete_project(project_id: int):
187    pool = await connect()
188    async with pool.acquire() as conn:
189        await conn.execute("""
190            UPDATE tasks SET completed = 1, completed_at = CURRENT_TIMESTAMP
191            WHERE project_id = $1
192        """, project_id)
193
194async def get_user_projects(user_id: int):
195    pool = await connect()
196    async with pool.acquire() as conn:
197        return await conn.fetch("SELECT id, title FROM projects WHERE user_id = $1", user_id)
198
199async def get_tasks_for_project(project_id: int):
200    pool = await connect()
201    async with pool.acquire() as conn:
202        return await conn.fetch("""
203            SELECT title, time, date, completed
204            FROM tasks
205            WHERE project_id = $1
206            ORDER BY date, time
207        """, project_id)
208
209async def get_user_projects_with_progress(user_id: int):
210    pool = await connect()
211    async with pool.acquire() as conn:
212        return await conn.fetch("""
213            SELECT p.id, p.title,
214                   COUNT(t.id) AS total,
215                   SUM(CASE WHEN t.completed = 1 THEN 1 ELSE 0 END) AS completed
216            FROM projects p
217            LEFT JOIN tasks t ON t.project_id = p.id
218            WHERE p.user_id = $1
219            GROUP BY p.id
220        """, user_id)
221
222async def delete_project(project_id: int):
223    pool = await connect()
224    async with pool.acquire() as conn:
225        await conn.execute("DELETE FROM tasks WHERE project_id = $1", project_id)
226        await conn.execute("DELETE FROM projects WHERE id = $1", project_id)
227
228async def get_completed_tasks_last_week(user_id: int):
229    one_week_ago = (datetime.now() - timedelta(days=7)).date()
230    pool = await connect()
231    async with pool.acquire() as conn:
232        return await conn.fetch("""
233            SELECT tasks.title, task_logs.timestamp
234            FROM task_logs
235            JOIN tasks ON task_logs.task_id = tasks.id
236            WHERE task_logs.user_id = $1 AND task_logs.action = 'done'
237            AND DATE(task_logs.timestamp) >= $2
238            ORDER BY task_logs.timestamp DESC
239        """, user_id, one_week_ago)
240
241async def get_all_user_ids():
242    pool = await connect()
243    async with pool.acquire() as conn:
244        rows = await conn.fetch("SELECT user_id FROM users")
245        return [row['user_id'] for row in rows]
246
247async def get_completed_tasks(user_id: int):
248    pool = await connect()
249    async with pool.acquire() as conn:
250        return await conn.fetch("""
251            SELECT tasks.title, task_logs.timestamp
252            FROM task_logs
253            JOIN tasks ON task_logs.task_id = tasks.id
254            WHERE task_logs.user_id = $1 AND task_logs.action = 'done'
255            ORDER BY task_logs.timestamp DESC
256        """, user_id)
257
