from __future__ import annotations

from auto_commenter.core.comment_bot import run
from auto_commenter.settings import SettingsError, get_settings
from auto_commenter.utils.database import CommentRepository


def main() -> None:
    try:
        settings = get_settings()
    except SettingsError as exc:
        print(f"Configuration error: {exc}")
        return

    repository = CommentRepository(settings.db_path)
    repository.init_schema()
    run(settings, repository)


if __name__ == "__main__":
    main()
