"""Telegram private-channel object storage.

Telegram is used as object storage; Firestore stores only small references.
The bot account must be an administrator in TELEGRAM_DB_CHANNEL_ID.
"""
from __future__ import annotations

import io
import json
from typing import Any

from aiogram import Bot, types
from aiogram.types import BufferedInputFile

from config import TELEGRAM_DB_CHANNEL_ID


class TelegramStorage:
    def __init__(self, bot: Bot, chat_id: int | str | None = None):
        self.bot = bot
        self.chat_id = chat_id if chat_id is not None else TELEGRAM_DB_CHANNEL_ID

    def _id(self) -> int:
        if not self.chat_id:
            raise RuntimeError("TELEGRAM_DB_CHANNEL_ID sozlanmagan.")
        return int(self.chat_id)

    async def save_audio(self, file_id: str, kind: str, filename: str | None = None) -> dict:
        """Persist the media in the DB channel and return channel message/file IDs."""
        if kind == "voice":
            msg = await self.bot.send_voice(chat_id=self._id(), voice=file_id, caption="STT AUDIO")
            return {"message_id": msg.message_id, "file_id": msg.voice.file_id}
        msg = await self.bot.send_audio(chat_id=self._id(), audio=file_id, caption=filename or "STT AUDIO")
        return {"message_id": msg.message_id, "file_id": msg.audio.file_id}

    async def save_json(self, payload: dict[str, Any], filename: str, caption: str = "") -> types.Message:
        raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        document = BufferedInputFile(raw, filename=filename)
        return await self.bot.send_document(chat_id=self._id(), document=document, caption=caption[:1024])

    async def download_file_id(self, file_id: str) -> bytes:
        file_info = await self.bot.get_file(file_id)
        out = io.BytesIO()
        await self.bot.download_file(file_info.file_path, out)
        return out.getvalue()

    async def load_json(self, file_id: str) -> dict[str, Any]:
        raw = await self.download_file_id(file_id)
        return json.loads(raw.decode("utf-8"))

    async def copy_to_user(self, user_chat_id: int, message_id: int) -> types.MessageId:
        return await self.bot.copy_message(
            chat_id=user_chat_id,
            from_chat_id=self._id(),
            message_id=message_id,
        )
