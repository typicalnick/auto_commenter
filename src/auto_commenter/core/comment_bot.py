from __future__ import annotations

import asyncio

import random
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict

from telethon import TelegramClient, events

from ..settings import ChannelConfig, Settings
from ..utils.database import CommentRepository


@dataclass
class ChannelRuntime:
    config: ChannelConfig
    source_entity: object
    send_as_entity: object


class AutoCommenter:
    """Event-driven bot that replies to channel posts with prepared templates."""

    def __init__(self, settings: Settings, repository: CommentRepository) -> None:
        self._settings = settings
        self._repository = repository
        self._client = TelegramClient(
            settings.session_name, settings.api_id, settings.api_hash
        )
        self._channels: Dict[int, ChannelRuntime] = {}

    async def setup(self) -> None:
        await self._client.start()

        for config in self._settings.channel_configs:
            source_entity = await self._client.get_entity(config.source)
            send_as_entity = await self._client.get_entity(config.send_as)

            self._channels[source_entity.id] = ChannelRuntime(
                config=config,
                source_entity=source_entity,
                send_as_entity=send_as_entity,
            )

        listen_ids = list(self._channels.keys())
        self._client.add_event_handler(
            self._on_new_message, events.NewMessage(chats=listen_ids)
        )

    async def run(self) -> None:
        await self.setup()
        usernames = [cfg.source for cfg in self._settings.channel_configs]
        print("Auto-commenter is listening to:", ", ".join(usernames))
        await self._client.run_until_disconnected()

    async def _on_new_message(self, event: events.NewMessage.Event) -> None:
        runtime = self._channels.get(event.chat_id)
        if runtime is None:
            return

        repository = self._repository
        settings = self._settings

        last_time = repository.get_last_comment_time(runtime.source_entity.id)
        if last_time is not None:
            now = datetime.utcnow()
            delta = now - last_time
            if delta < timedelta(days=settings.min_days_between_comments):
                remaining = timedelta(days=settings.min_days_between_comments) - delta
                remaining_days = remaining.days
                print(
                    f"[SKIP] {runtime.config.source}: last comment {last_time}, "
                    f"wait {max(remaining_days, 0)} more days."
                )
                return

        used_templates = repository.get_used_templates_recently(
            runtime.source_entity.id,
            within_days=settings.template_cooldown_days,
        )
        available_indexes = [
            idx
            for idx in range(len(runtime.config.templates))
            if idx not in used_templates
        ]
        if not available_indexes:
            print(
                f"[SKIP] {runtime.config.source}: all templates were used in the last "
                f"{settings.template_cooldown_days} days."
            )
            return

        template_index = random.choice(available_indexes)
        text = runtime.config.templates[template_index]

        try:
            await self._client.send_message(
                entity=event.chat_id,
                message=text,
                comment_to=event.id,
                send_as=runtime.send_as_entity,
            )
        except Exception as exc:  # pragma: no cover - Telethon specific errors
            print(f"[ERROR] Failed to send comment: {exc}")
            return

        repository.log_comment(
            source_channel_id=runtime.source_entity.id,
            source_username=getattr(runtime.source_entity, "username", None),
            send_as_id=runtime.send_as_entity.id,
            send_as_username=getattr(runtime.send_as_entity, "username", None),
            post_id=event.id,
            template_index=template_index,
            text=text,
        )

        print(
            f"[OK] {runtime.config.source} <- {runtime.config.send_as}: '{text}' "
            f"(post_id={event.id}, template_index={template_index})"
        )


async def run_bot(settings: Settings, repository: CommentRepository) -> None:
    bot = AutoCommenter(settings, repository)
    await bot.run()


def run(settings: Settings, repository: CommentRepository) -> None:
    asyncio.run(run_bot(settings, repository))
