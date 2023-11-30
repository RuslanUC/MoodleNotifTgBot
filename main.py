from json import dumps, loads
from typing import Union

import aiocron
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, CallbackQuery
from tortoise import Tortoise

from config import USERS_LIMIT_PER_TG_USER, API_ID, API_HASH, BOT_TOKEN, DATABASE_URL
from models import User
from models.session import Session
from models.tg_user import TgUser
from moodle_api import MoodleApi
from utils import send_to_users, text_filter, edit_or_send
from utils.pyrogram_wait_for_message import WaitForMessage

bot = Client(
    name="MoodleNotifBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
)
wait = WaitForMessage(bot)


@bot.on_message(filters.private & filters.command(["start"]))
async def command_start(cl: Client, message: Message):
    await bot.send_message(
        message.chat.id, "Click buttons to add or view your users", reply_markup=ReplyKeyboardMarkup([
            ["Add User", "My Users"],
        ], resize_keyboard=True, is_persistent=True)
    )


@bot.on_message(filters.private & (filters.command(["auth"]) | text_filter("Add User")))
async def command_auth(cl: Client, message: Message):
    chat = message.chat
    tg_user, _ = await TgUser.get_or_create(id=message.from_user.id)
    if await tg_user.moodle_users.all().count() >= USERS_LIMIT_PER_TG_USER:
        return await cl.send_message(chat.id, f"You can't add more than {USERS_LIMIT_PER_TG_USER} users!")

    login_message_req = await cl.send_message(chat.id, "Send your email:")
    login_message = await wait.wait_for(chat)
    password_message_req = await cl.send_message(chat.id, "Send your password:")
    password_message = await wait.wait_for(chat)
    login = login_message.text
    password = password_message.text

    auth_message = await cl.send_message(chat.id, "Authenticating...")
    user = await User.get_or_none(login=login)
    try:
        moodle = await MoodleApi.login(login, password)
        name = await moodle.get_name()
    except:
        return await auth_message.edit_text(f"Failed to authenticate!")
    if not moodle:
        if user is not None and user.password == password:
            await user.delete()
        return await auth_message.edit_text(f"Failed to authenticate!")

    name = name or "Unknown"

    if user is not None and user.password != password:
        user.password = password
        await user.save()

    for msg in (password_message, password_message_req, login_message, login_message_req):
        await msg.delete()

    user, _ = await User.get_or_create(defaults={"login": login, "password": password, "name": name}, id=moodle.user_id)
    if not await tg_user.moodle_users.filter(id=user.id).exists():
        await tg_user.moodle_users.add(user)

    await Session.create(user=user, session_id=moodle.session_id, session_key=moodle.session_key)
    await auth_message.edit_text(f"Authenticated!")


@bot.on_message(filters.private & (filters.command(["users"]) | text_filter("My Users")))
async def command_users(cl: Client, message: Message):
    await list_users(cl, message)


async def list_users(cl: Client, message: Union[Message, CallbackQuery], existing_message: Message = None):
    chat = message.chat if isinstance(message, Message) else message.message.chat
    tg_user, _ = await TgUser.get_or_create(id=message.from_user.id)
    users = await tg_user.moodle_users.all()
    if not users:
        return await edit_or_send(cl, chat, existing_message, text="You don't have any users")

    return await edit_or_send(
        cl, chat, existing_message, text="Here are your users:", reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(user.name, callback_data=dumps({"t": 1, "u": user.id}))] for user in users
        ])
    )


async def answer_query_sel_user(cl: Client, callback_query: CallbackQuery, user_id: int):
    tg_user, _ = await TgUser.get_or_create(id=callback_query.from_user.id)
    if not (user := await tg_user.moodle_users.filter(id=user_id).get_or_none()):
        return

    await callback_query.message.edit_text(
        f"Selected user: {user.name} ({user.login})",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Delete", callback_data=dumps({"t": 2, "u": user.id}))],
            [InlineKeyboardButton("Back", callback_data=dumps({"t": 0}))],
        ])
    )


async def answer_query_del_user(cl: Client, callback_query: CallbackQuery, user_id: int):
    tg_user, _ = await TgUser.get_or_create(id=callback_query.from_user.id)
    if not (user := await tg_user.moodle_users.filter(id=user_id).get_or_none()):
        return

    await tg_user.moodle_users.remove(user)

    await list_users(cl, callback_query, callback_query.message)


@bot.on_callback_query()
async def answer_query(cl: Client, callback_query: CallbackQuery):
    try:
        data = loads(callback_query.data)
        if data["t"] == 0:
            await list_users(cl, callback_query, callback_query.message)
        elif data["t"] == 1:
            await answer_query_sel_user(cl, callback_query, data["u"])
        elif data["t"] == 2:
            await answer_query_del_user(cl, callback_query, data["u"])
    except (ValueError, KeyError):
        return


@aiocron.crontab('*/5 * * * *')
async def check_notifications_task():
    for user in await User.all():
        if await user.tgusers.all().count() == 0:
            continue

        session = await Session.filter(user=user).select_related("user").order_by("-id").first()
        if session is None or not await MoodleApi.touch_session(session):
            moodle = await MoodleApi.login(user.login, user.password)
            await Session.create(user=user, session_id=moodle.session_id, session_key=moodle.session_key)
        else:
            moodle = MoodleApi(user.id, session.session_id, session.session_key)

        tg_users = await user.tgusers.all()
        for notification in await moodle.getNotifications():
            await send_to_users(bot, tg_users, text=str(notification), reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("Open", url=notification.url),
            ]]))


if __name__ == "__main__":
    _start = bot.start


    async def _new_start():
        await Tortoise.init(db_url=DATABASE_URL, modules={"models": ["models"]})
        await Tortoise.generate_schemas()

        print("Bot running!")
        await _start()


    bot.start = _new_start
    bot.run()
