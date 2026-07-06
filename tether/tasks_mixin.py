"""Tasks mixin for SQLiteRuntime — the lightweight shared task board (tether_tasks).

Mixed into SQLiteRuntime. Relies on the host class to provide `self._conn` (the SQLite
connection) — that's the mixin contract. Owns its own schema via `_init_tasks_db`, which
the host calls during construction. Distinct from the smart board (tickets / CORE-N
lifecycle in board_mixin); this is the simpler task list with comments.
"""

from datetime import datetime, timezone
from typing import Any, List, Optional


class TasksMixin:
    def _init_tasks_db(self):
        """Initialize shared task board tables (v1.5)."""
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS tether_tasks (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT DEFAULT '',
                status TEXT DEFAULT 'open',
                priority TEXT DEFAULT 'p1',
                assignee TEXT DEFAULT 'unassigned',
                created_by TEXT,
                created_at TEXT,
                updated_at TEXT,
                tags TEXT
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS tether_task_comments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL,
                author TEXT NOT NULL,
                text TEXT NOT NULL,
                created_at TEXT,
                FOREIGN KEY (task_id) REFERENCES tether_tasks(id)
            )
        """)
        self._conn.commit()

    def task_create(self, id: str, title: str, description: str = '',
                    priority: str = 'p1', assignee: str = 'unassigned',
                    created_by: str = 'unknown', tags: Optional[List[str]] = None) -> dict:
        """Create a new task. Raises ValueError if id already exists."""
        now = datetime.now(timezone.utc).isoformat()
        tags_str = ','.join(tags) if tags else ''
        self._conn.execute(
            "INSERT INTO tether_tasks "
            "(id, title, description, status, priority, assignee, created_by, created_at, updated_at, tags) "
            "VALUES (?, ?, ?, 'open', ?, ?, ?, ?, ?, ?)",
            (id, title, description, priority, assignee, created_by, now, now, tags_str)
        )
        self._conn.commit()
        return self.task_get(id)

    def task_update(self, id: str, status: Optional[str] = None,
                    priority: Optional[str] = None, assignee: Optional[str] = None,
                    description: Optional[str] = None, title: Optional[str] = None,
                    tags: Optional[List[str]] = None) -> dict:
        """Update mutable fields on a task."""
        allowed = {'status': status, 'priority': priority, 'assignee': assignee,
                   'description': description, 'title': title}
        updates = {k: v for k, v in allowed.items() if v is not None}
        if tags is not None:
            updates['tags'] = ','.join(tags)
        if not updates:
            return self.task_get(id)
        updates['updated_at'] = datetime.now(timezone.utc).isoformat()
        set_clause = ', '.join(f"{k} = ?" for k in updates)
        self._conn.execute(
            f"UPDATE tether_tasks SET {set_clause} WHERE id = ?",
            list(updates.values()) + [id]
        )
        self._conn.commit()
        return self.task_get(id)

    def task_list(self, status: Optional[str] = None, assignee: Optional[str] = None,
                  priority: Optional[str] = None) -> List[dict]:
        """List tasks with optional filters. Returns summary rows (no comments)."""
        query = "SELECT * FROM tether_tasks WHERE 1=1"
        params: List[Any] = []
        if status:
            query += " AND status = ?"; params.append(status)
        if assignee:
            query += " AND assignee = ?"; params.append(assignee)
        if priority:
            query += " AND priority = ?"; params.append(priority)
        query += " ORDER BY priority ASC, created_at ASC"
        tasks = []
        for row in self._conn.execute(query, params):
            t = dict(row)
            t['tags'] = [x for x in t['tags'].split(',') if x] if t['tags'] else []
            tasks.append(t)
        return tasks

    def task_get(self, id: str) -> dict:
        """Get a single task with full comment history."""
        cursor = self._conn.execute("SELECT * FROM tether_tasks WHERE id = ?", (id,))
        row = cursor.fetchone()
        if not row:
            raise ValueError(f"Task not found: {id}")
        task = dict(row)
        task['tags'] = [x for x in task['tags'].split(',') if x] if task['tags'] else []
        comments_cursor = self._conn.execute(
            "SELECT author, text, created_at FROM tether_task_comments "
            "WHERE task_id = ? ORDER BY created_at ASC", (id,)
        )
        task['comments'] = [dict(c) for c in comments_cursor]
        return task

    def task_comment(self, id: str, author: str, text: str) -> dict:
        """Append a comment to a task. Bumps updated_at on the task."""
        self.task_get(id)  # raises if not found
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            "INSERT INTO tether_task_comments (task_id, author, text, created_at) VALUES (?, ?, ?, ?)",
            (id, author, text, now)
        )
        self._conn.execute("UPDATE tether_tasks SET updated_at = ? WHERE id = ?", (now, id))
        self._conn.commit()
        return self.task_get(id)
