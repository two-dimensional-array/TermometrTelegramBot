from termometr import TermometerHandler

from aiogram import Bot, Dispatcher, Router
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery, Update
from aiogram.filters import Command, CommandStart
from aiogram.client.session.aiohttp import AiohttpSession

import asyncio

class TermometerBot():
    def __init__(self, termometers: TermometerHandler, token: str, proxy: str):
        self.session = AiohttpSession(proxy=proxy)
        self.bot = Bot(token=token, session=self.session)
        self.termometers = termometers
        self.router = Router()
        self.dp = Dispatcher()
        self.dp.include_router(self.router)

        # 2. Register handlers manually to bind them to 'self'
        self.router.message.register(self.start_handler, CommandStart())
        self.router.message.register(self.termometers_handler, Command("termometers"))
        self.router.message.register(self.list_handler, Command("list"))
        self.router.callback_query.register(self.termometer_callback)

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

    def __build_termometers_keyboard(self):
        """Build an inline keyboard with one button per termometer (uses termometer id in callback).

        Returns InlineKeyboardMarkup.
        """
        # aiogram v3 expects the InlineKeyboardMarkup to be constructed with an
        # `inline_keyboard` list of button rows (each row is a list of buttons).
        buttons = [[InlineKeyboardButton(text=t.name, callback_data=f"term_{t.id}")] for t in self.termometers.get_all_termometrs()]
        return InlineKeyboardMarkup(inline_keyboard=buttons)

    async def __send_termometers_keyboard(self, message: Message):
        """Internal helper: send keyboard with all termometers and log actions."""
        print(f"__send_termometers_keyboard invoked by {getattr(message.from_user, 'id', 'unknown')}")
        try:
            if not self.termometers.get_all_termometrs():
                await message.answer("No termometers available.")
                return
            kb = self.__build_termometers_keyboard()
            await message.answer("Select a termometer:", reply_markup=kb)
        except Exception as e:
            print(f"Error sending termometers keyboard: {e}")
            # try to inform user
            try:
                await message.answer("Sorry, failed to display termometers.")
            except Exception as _:
                pass

    async def start_handler(self, message: Message):
        print("/start handler called")
        await self.__send_termometers_keyboard(message)

    async def termometers_handler(self, message: Message):
        print("/termometers handler called")
        await self.__send_termometers_keyboard(message)

    async def list_handler(self, message: Message):
        print("/list handler called")
        await self.__send_termometers_keyboard(message)

    async def termometer_callback(self, callback: CallbackQuery):
        """Handle termometer selection from inline keyboard and send readings."""
        data = callback.data or ""
        if not data.startswith("term_"):
            await callback.answer()
            return
        term_id = data.split("term_", 1)[1]
        term = next((t for t in self.termometers.get_all_termometrs() if str(t.id) == str(term_id)), None)
        if term is None:
            await callback.answer("Termometer not found.", show_alert=True)
            return

        text = (f"*{term.name}*\n"
                f"Temperature: \t{term.temperature:.2f} °C\n"
                f"Humidity: \t{term.humidity:.2f} %")
        # send a message to the user who pressed the button
        await callback.message.answer(text, parse_mode="Markdown")
        # dismiss the loading state of the inline button
        await callback.answer()
