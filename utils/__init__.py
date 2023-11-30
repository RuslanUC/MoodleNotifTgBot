from pyrogram import Client
from pyrogram.filters import create
from pyrogram.types import Message, Chat

from models import TgUser


async def send_to_users(bot: Client, users: list[TgUser], **message_kwargs):
    for user in users:
        await bot.send_message(user.id, **message_kwargs)


def text_filter(text: str):
    async def func(flt, __, m: Message):
        return m.text == flt.text

    return create(func, "MessageTextFilter", text=text)


async def edit_or_send(bot: Client, chat: Chat, message: Message=None, **message_kwargs):
    if message:
        return await message.edit_text(**message_kwargs)
    await bot.send_message(chat.id, **message_kwargs)
