from termometr import TermometerHandler
from user import UserStorage

from aiogram import Bot, Dispatcher, Router, BaseMiddleware
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery, Update, TelegramObject
from aiogram.filters import Command, CommandStart
from aiogram.client.session.aiohttp import AiohttpSession
from typing import Callable, Dict, Any, Awaitable
import asyncio

class AccessMiddleware(BaseMiddleware):
    def __init__(self, users: UserStorage):
        super().__init__()
        self.users = users

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any]
    ) -> Any:
        if self.users.find_user_by_id(event.from_user.id) is None:
            return

        return await handler(event, data)

class TermometerBot():
    def __init__(self, termometers: TermometerHandler, users: UserStorage, token: str, proxy: str):
        self.session = AiohttpSession(proxy=proxy)
        self.bot = Bot(token=token, session=self.session)
        self.termometers = termometers
        self.users = users
        self.router = Router()
        self.dp = Dispatcher()

        self.dp.include_router(self.router)
        self.router.message.register(self.start_handler, CommandStart())
        self.router.message.register(self.termometers_handler, Command("termometers"))
        self.router.message.register(self.list_handler, Command("list"))
        self.router.callback_query.register(self.termometer_callback)

        self.dp.message.outer_middleware(AccessMiddleware(self.users))

    def set_webhook(self, webhook_url: str):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            # Delete old webhook and set new one
            loop.run_until_complete(self.bot.delete_webhook(drop_pending_updates=True))
            success = loop.run_until_complete(self.bot.set_webhook(webhook_url))
        finally:
            loop.close()

        return success

    def webhook_handler(self, data: dict):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            update = Update.model_validate(data, context={"bot": self.bot})
            loop.run_until_complete(self.dp.feed_update(self.bot, update))
        finally:
            loop.run_until_complete(self.bot.session.close())
            loop.close()

    async def __delete_previous_message(self, user_id: int):
        """Delete the previous message sent by the bot to the user."""
        try:
            user_data = self.users.find_user_by_id(user_id)
            print(user_data)
            if user_data is not None:
                await self.bot.delete_message(chat_id=int(user_data["chat_id"]), message_id=int(user_data["last_msg_id"]))
        except Exception as e:
            print(f"Failed to delete previous message for user {user_id}: {e}")

    def __build_termometers_keyboard(self, user_id):
        """Build an inline keyboard with one button per termometer (uses termometer id in callback).

        Returns InlineKeyboardMarkup.
        """
        # aiogram v3 expects the InlineKeyboardMarkup to be constructed with an
        # `inline_keyboard` list of button rows (each row is a list of buttons).
        buttons = [[InlineKeyboardButton(text=t.name, callback_data=f"term_{t.id}_{user_id}")] for t in self.termometers.get_all_termometrs()]
        return InlineKeyboardMarkup(inline_keyboard=buttons)

    async def __send_termometers_keyboard(self, message: Message, user_id=None):
        """Internal helper: send keyboard with all termometers and log actions."""
        if user_id is None:
            user_id = message.from_user.id

        print(f"__send_termometers_keyboard invoked by {user_id}")
        try:
            await self.__delete_previous_message(user_id)

            if not self.termometers.get_all_termometrs():
                sent_message = await message.answer("No termometers available.")
                self.users.set_last_msg_id(user_id, sent_message.message_id, sent_message.chat.id)
                return

            kb = self.__build_termometers_keyboard(user_id)
            sent_message = await message.answer("Select a termometer:", reply_markup=kb)
            self.users.set_last_msg_id(user_id, sent_message.message_id, sent_message.chat.id)
        except Exception as e:
            print(f"Error sending termometers keyboard: {e}")
            # try to inform user
            try:
                sent_message = await message.answer("Sorry, failed to display termometers.")
                self.users.set_last_msg_id(user_id, sent_message.message_id, sent_message.chat.id)
            except Exception as _:
                pass

    async def start_handler(self, message: Message):
        print("/start handler called")
        await message.delete()
        await self.__send_termometers_keyboard(message)

    async def termometers_handler(self, message: Message):
        print("/termometers handler called")
        await message.delete()
        await self.__send_termometers_keyboard(message)

    async def list_handler(self, message: Message):
        print("/list handler called")
        await message.delete()
        await self.__send_termometers_keyboard(message)

    async def termometer_callback(self, callback: CallbackQuery):
        """Handle termometer selection from inline keyboard and send readings, with a return button."""
        data = callback.data or ""
        if data.startswith("back_to_list_"):
            # Return to the termometer list
            user_id = int(data[13:])
            await self.__delete_previous_message(user_id)
            await self.__send_termometers_keyboard(callback.message, user_id)
            await callback.answer()
            return

        if not data.startswith("term_"):
            await callback.answer()
            return

        term_data = data[5:].split("_")
        term_id = int(term_data[0])
        user_id = int(term_data[1])
        term = self.termometers.find_termometr_by_id(term_id)
        if term is None:
            await callback.answer("Termometer not found.", show_alert=True)
            return

        text = (f"*{term.name}*\nTemperature: \t{float(term.temperature):.2f} °C\nHumidity: \t{float(term.humidity):.2f} %")
        # Add a button to return to the list
        back_kb = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="⬅️ Back to list", callback_data=f"back_to_list_{user_id}")]]
        )
        await self.__delete_previous_message(user_id)
        sent_message = await callback.message.answer(text, parse_mode="Markdown", reply_markup=back_kb)
        self.users.set_last_msg_id(user_id, sent_message.message_id, sent_message.chat.id)
        await callback.answer()
