from asyncio import Future, Lock
from dataclasses import dataclass

from pyrogram import Client
from pyrogram.handlers import MessageHandler
from pyrogram.types import Chat, Message


class WaitForMessage:
    def __init__(self, client: Client):
        self._client = client
        self._handlers: dict[int, list[Future]] = {}
        self._locks: dict[int, Lock] = {}

        client.add_handler(MessageHandler(self._listener), group=1)

    async def _listener(self, _: Client, message: Message) -> None:
        chat_id = message.chat.id
        if chat_id not in self._handlers:
            return

        self._locks[chat_id] = lock = self._locks.get(chat_id, Lock())
        async with lock:
            for future in self._handlers[chat_id]:
                future.set_result(message)

            self._handlers[chat_id].clear()

    def wait_for(self, chat: Chat) -> Future[Message]:
        future = self._client.loop.create_future()
        if chat.id not in self._handlers:
            self._handlers[chat.id] = []

        self._handlers[chat.id].append(future)
        return future
