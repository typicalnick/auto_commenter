import asyncio
import random
import sqlite3
from datetime import datetime, timedelta

from telethon import TelegramClient, events

# ============ НАСТРОЙКИ ============

API_ID = 123456          # твой api_id с https://my.telegram.org
API_HASH = "your_api_hash"
SESSION_NAME = "auto_commenter"

DB_PATH = "comments.db"

# Конфиг: какие каналы слушаем и от какого канала там отвечаем
# source  — канал, из которого ловим посты
# send_as — канал, ОТ ИМЕНИ которого пишем комментарии
CONFIG = [
    {
        "source": "some_source_channel_1",   # @username или t.me/...
        "send_as": "your_comment_channel",   # твой канал, от имени которого пишем
        "templates": [
            "Классный разбор, спасибо!",
            "Очень полезный пост, забрал себе 🔖",
            "Как раз думал об этом вчера, попали в точку 🙂",
        ],
    },
    {
        "source": "some_source_channel_2",
        "send_as": "your_comment_channel",
        "templates": [
            "Интересный взгляд, спасибо за инсайт!",
            "Вот за такие посты и люблю этот канал ❤️",
        ],
    },
]

# Ограничения
MIN_DAYS_BETWEEN_COMMENTS = 7       # минимум 7 дней между комментариями в одном канале
TEMPLATE_COOLDOWN_DAYS = 45         # не повторяем шаблон в канале 45 дней


# ============ РАБОТА С БД ============

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
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
        )
        """
    )
    conn.commit()
    conn.close()


def log_comment(source_channel_id, source_username,
                send_as_id, send_as_username,
                post_id, template_index, text):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO comment_log (
            source_channel_id, source_channel_username,
            send_as_channel_id, send_as_username,
            post_id, template_index, text, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            source_channel_id,
            source_username,
            send_as_id,
            send_as_username,
            post_id,
            template_index,
            text,
            datetime.utcnow().isoformat(),
        ),
    )
    conn.commit()
    conn.close()


def get_last_comment_time(source_channel_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT MAX(created_at) FROM comment_log
        WHERE source_channel_id = ?
        """,
        (source_channel_id,),
    )
    row = cur.fetchone()
    conn.close()
    if not row or not row[0]:
        return None
    return datetime.fromisoformat(row[0])


def get_used_templates_recently(source_channel_id, days=TEMPLATE_COOLDOWN_DAYS):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cutoff = datetime.utcnow() - timedelta(days=days)
    cur.execute(
        """
        SELECT DISTINCT template_index FROM comment_log
        WHERE source_channel_id = ?
          AND created_at >= ?
        """,
        (source_channel_id, cutoff.isoformat()),
    )
    rows = cur.fetchall()
    conn.close()
    return {r[0] for r in rows}


# ============ ОСНОВНОЙ СКРИПТ ============

async def main():
    init_db()

    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    await client.start()

    # Подготовим мапу: source_peer_id -> конфиг и сущности
    source_map = {}  # chat_id -> {config, source_entity, send_as_entity}

    # Разрешим слушать каналы по их @username
    source_usernames = [c["source"] for c in CONFIG]

    # Заранее получаем сущности каналов
    for conf in CONFIG:
        source_entity = await client.get_entity(conf["source"])
        send_as_entity = await client.get_entity(conf["send_as"])

        source_map[source_entity.id] = {
            "config": conf,
            "source_entity": source_entity,
            "send_as_entity": send_as_entity,
        }

    # Список id каналов, которые слушаем
    listen_ids = list(source_map.keys())

    @client.on(events.NewMessage(chats=listen_ids))
    async def handler(event: events.NewMessage.Event):
        chat_id = event.chat_id
        if chat_id not in source_map:
            return  # на всякий случай

        meta = source_map[chat_id]
        conf = meta["config"]
        source_entity = meta["source_entity"]
        send_as_entity = meta["send_as_entity"]

        # 1. Проверяем ограничение по времени (7 дней с последнего комментария в этот канал)
        last_time = get_last_comment_time(source_entity.id)
        if last_time is not None:
            if datetime.utcnow() - last_time < timedelta(days=MIN_DAYS_BETWEEN_COMMENTS):
                # Слишком рано, выходим
                print(
                    f"[SKIP] Канал {source_entity.username}: последний комментарий {last_time}, еще не прошло 7 дней."
                )
                return

        # 2. Выбор шаблона, который не использовался 45 дней в этом канале
        templates = conf["templates"]
        used_indexes = get_used_templates_recently(source_entity.id)
        available_indexes = [
            i for i in range(len(templates)) if i not in used_indexes
        ]

        if not available_indexes:
            print(
                f"[SKIP] Канал {source_entity.username}: все шаблоны уже использованы за последние {TEMPLATE_COOLDOWN_DAYS} дней."
            )
            return

        template_index = random.choice(available_indexes)
        text = templates[template_index]

        # 3. Отправляем комментарий ПОД постом
        # comment_to=event.id — делаем ответ в комментариях к посту
        # send_as=send_as_entity — от имени канала
        try:
            msg = await client.send_message(
                entity=event.chat_id,
                message=text,
                comment_to=event.id,     # важное место: пишем КАК КОММЕНТАРИЙ
                send_as=send_as_entity,  # важное место: пишем ОТ ИМЕНИ КАНАЛА
            )
        except Exception as e:
            print(f"[ERROR] Не удалось отправить комментарий: {e}")
            return

        # 4. Логируем в БД
        log_comment(
            source_channel_id=source_entity.id,
            source_username=getattr(source_entity, "username", None),
            send_as_id=send_as_entity.id,
            send_as_username=getattr(send_as_entity, "username", None),
            post_id=event.id,
            template_index=template_index,
            text=text,
        )

        print(
            f"[OK] Комментарий в {source_entity.username} "
            f"от {send_as_entity.username}: '{text}' "
            f"(post_id={event.id}, template_index={template_index})"
        )

    print("Бот запущен, слушаем каналы:", source_usernames)
    await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())
