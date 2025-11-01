#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import asyncio
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from config import BOT_TOKEN, log, ADMINS            
from db import ensure_schema
from handlers.basic import router as basic_router
from handlers.fun import router as fun_router
from handlers.moderation import router as moderation_router
from handlers.schedule import router as schedule_router, start_background_tasks
from handlers.alerts import router as alerts_router
from handlers.misc import router as misc_router

from bot_commands import register_bot_commands, dump_commands_to_text  

async def notify_admins_startup(bot: Bot, text: str):  
    for uid in ADMINS:
        try:
            await bot.send_message(uid, f"🤖 Бот перезапущено.\n\n{text}")
        except Exception:
            pass

async def main():
    ensure_schema()
    bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()

    dp.include_router(basic_router)
    dp.include_router(fun_router)
    dp.include_router(moderation_router)
    dp.include_router(schedule_router)
    dp.include_router(alerts_router)
    dp.include_router(misc_router)

    me = await bot.get_me()

   #1) command menu
    await register_bot_commands(bot)

   
# 2) in the log and (optionally) admins
    commands_text = await dump_commands_to_text(bot)
    log.info("Registered bot commands:\n" + commands_text)
    await notify_admins_startup(bot, commands_text)

    log.info(f"Started as @{me.username} (id={me.id})")

   
#3) Background tasks
    start_background_tasks(bot)

#4) polling
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        log.info("Bot stopped")
