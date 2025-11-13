from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Generator, Iterable, Set


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS comment_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_channel_id INTEGER NOT NULL,
    source_channel_username TEXT,
    send_as_channel_id INTEGER NOT NULL,
    send_as_username TEXT,
    post_id INTEGER NOT NULL,
    template_index INTEGER NOT NULL,
    text TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL
);
"""


class CommentRepository:
    """Simple repository for persisting comment history."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    @contextmanager
    def _connect(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(self._db_path)
        try:
            yield conn
        finally:
            conn.close()

    def init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(SCHEMA_SQL)
            conn.commit()

    def execute_script(self, sql: str) -> None:
        with self._connect() as conn:
            conn.executescript(sql)
            conn.commit()

    def log_comment(
        self,
        *,
        source_channel_id: int,
        source_username: str | None,
        send_as_id: int,
        send_as_username: str | None,
        post_id: int,
        template_index: int,
        text: str,
    ) -> None:
        payload = (
            source_channel_id,
            source_username,
            send_as_id,
            send_as_username,
            post_id,
            template_index,
            text,
            datetime.utcnow().isoformat(),
        )
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO comment_log (
                    source_channel_id,
                    source_channel_username,
                    send_as_channel_id,
                    send_as_username,
                    post_id,
                    template_index,
                    text,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                payload,
            )
            conn.commit()

    def get_last_comment_time(self, source_channel_id: int) -> datetime | None:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                SELECT MAX(created_at)
                FROM comment_log
                WHERE source_channel_id = ?
                """,
                (source_channel_id,),
            )
            row = cursor.fetchone()

        if not row or not row[0]:
            return None
        return datetime.fromisoformat(row[0])

    def get_used_templates_recently(
        self, source_channel_id: int, *, within_days: int
    ) -> Set[int]:
        cutoff = datetime.utcnow() - timedelta(days=within_days)
        with self._connect() as conn:
            cursor = conn.execute(
                """
                SELECT DISTINCT template_index
                FROM comment_log
                WHERE source_channel_id = ?
                  AND created_at >= ?
                """,
                (source_channel_id, cutoff.isoformat()),
            )
            rows: Iterable[tuple[int]] = cursor.fetchall()
        return {row[0] for row in rows}

