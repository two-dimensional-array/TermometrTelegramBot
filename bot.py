from termometr import TermometerHandler
from user import UserStorage

from aiogram import Bot, Dispatcher, Router, BaseMiddleware
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery, Update, TelegramObject
from aiogram.filters import CommandStart
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.exceptions import TelegramBadRequest
from typing import Callable, Dict, Any, Awaitable
import asyncio
from enum import Enum

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
    class CallBackType(Enum):
        SHOW_TERMOMETER_INFO      = "terminfo"
        RETURN_TO_TERMOMETER_LIST = "backtermlist"

        def get_callback_data(self, user_id: int, arguments=None) -> str:
            result = f"{self.value},{user_id}"
            if arguments is not None:
                for arg in arguments:
                    result = result + f",{arg}"
            print(result)
            return result

    def __init__(self, termometers: TermometerHandler, users: UserStorage, token: str, proxy: str):
        self.session = AiohttpSession(proxy=proxy)
        self.bot = Bot(token=token, session=self.session)
        self.termometers = termometers
        self.users = users
        self.router = Router()
        self.dp = Dispatcher()

        self.dp.include_router(self.router)
        self.router.message.register(self.start_handler, CommandStart())
        self.router.callback_query.register(self.callback_handler)

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

    async def __message_answer(self, message: Message, user_id: int, text:str, reply_markup=None):
        user = self.users.find_user_by_id(user_id)
        if user is not None:
            if not await self.__edit_previous_message(user, text, reply_markup):
                await self.__delete_previous_message(user)
                sent_message = await message.answer(text, parse_mode="Markdown", reply_markup=reply_markup)
                self.users.set_last_msg_id(user_id, sent_message.message_id, sent_message.chat.id)

    async def __delete_previous_message(self, user: dict) -> bool:
        """Delete the previous message sent by the bot to the user."""
        try:
            await self.bot.delete_message(chat_id=int(user["chat_id"]), message_id=int(user["last_msg_id"]))
            return True
        except Exception as e:
            print(f"Failed to delete previous message with id {user['last_msg_id']} for user {user['user_id']}: {e}")
            return False

    async def __edit_previous_message(self, user: dict, text:str, reply_markup=None) -> bool:
        """Edit the previous message sent by the bot to the user."""
        try:
            await self.bot.edit_message_text(text=text, parse_mode="Markdown", reply_markup=reply_markup, chat_id=int(user["chat_id"]), message_id=int(user["last_msg_id"]))
            return True
        except TelegramBadRequest as e:
            if "message is not modified" in str(e):
                return True
            else:
                print(f"Failed to edit previous message with id {user['last_msg_id']} for user {user['user_id']}: {e}")
                return False
        except Exception as e:
            print(f"Failed to edit previous message with id {user['last_msg_id']} for user {user['user_id']}: {e}")
            return False

    def __build_termometers_keyboard(self, user_id):
        """Build an inline keyboard with one button per termometer (uses termometer id in callback).

        Returns InlineKeyboardMarkup.
        """
        buttons = [[InlineKeyboardButton(
            text=t.name,
            callback_data=self.CallBackType.SHOW_TERMOMETER_INFO.get_callback_data(user_id, [t.id])
        )] for t in self.termometers.get_all_termometrs()]
        return InlineKeyboardMarkup(inline_keyboard=buttons)

    def __build_termometer_menu_keyboard(self, user_id: int, term_id: int):
        return InlineKeyboardMarkup(
            inline_keyboard=[[
                InlineKeyboardButton(
                    text="⬅️ Back to list",
                    callback_data=self.CallBackType.RETURN_TO_TERMOMETER_LIST.get_callback_data(user_id)
                ),
                InlineKeyboardButton(
                    text="Update",
                    callback_data=self.CallBackType.SHOW_TERMOMETER_INFO.get_callback_data(user_id, [term_id])
                )
            ]]
        )

    async def __send_termometers_keyboard(self, message: Message, user_id=None):
        """Internal helper: send keyboard with all termometers and log actions."""
        if user_id is None:
            user_id = message.from_user.id

        print(f"__send_termometers_keyboard invoked by {user_id}")
        try:
            if not self.termometers.get_all_termometrs():
                await self.__message_answer(message, user_id, "No termometers available.")
                return

            kb = self.__build_termometers_keyboard(user_id)
            await self.__message_answer(message, user_id, "Select a termometer:", reply_markup=kb)
        except Exception as e:
            print(f"Error sending termometers keyboard: {e}")
            try:
                await self.__message_answer(message, user_id, "Sorry, failed to display termometers.")
            except Exception as _:
                pass

    async def start_handler(self, message: Message):
        print("/start handler called")
        await message.delete()
        await self.__send_termometers_keyboard(message)

    async def callback_handler(self, callback: CallbackQuery):
        try:
            data = callback.data.split(",")
            event = self.CallBackType(data[0])
            user_id = int(data[1])

            if event == self.CallBackType.SHOW_TERMOMETER_INFO:
                term_id = int(data[2])
                term = self.termometers.find_termometr_by_id(term_id)
                if term is None:
                    await callback.answer("Termometer not found.", show_alert=True)
                else:
                    text = f"*{term.name}*\nTemperature: {float(term.temperature):.2f}°C\nHumidity: {float(term.humidity):.2f} %"
                    back_kb = self.__build_termometer_menu_keyboard(user_id, term_id)
                    await self.__message_answer(callback.message, user_id, text, reply_markup=back_kb)
            elif event == self.CallBackType.RETURN_TO_TERMOMETER_LIST:
                await self.__send_termometers_keyboard(callback.message, user_id)
        except Exception as _:
            pass

        await callback.answer()
