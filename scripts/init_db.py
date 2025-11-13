from __future__ import annotations

from pathlib import Path

from auto_commenter.settings import get_settings
from auto_commenter.utils.database import CommentRepository


def apply_migrations() -> None:
    settings = get_settings()
    repo = CommentRepository(settings.db_path)
    repo.init_schema()

    migrations_dir = Path(__file__).resolve().parents[1] / "migrations"
    for path in sorted(migrations_dir.glob("*.sql")):
        sql = path.read_text(encoding="utf-8")
        if not sql.strip():
            continue
        repo.execute_script(sql)
        print(f"Applied migration: {path.name}")


if __name__ == "__main__":
    apply_migrations()
