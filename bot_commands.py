# bot_commands.py
from typing import List

from aiogram.types import (
    BotCommand,
    BotCommandScopeAllChatAdministrators,
    BotCommandScopeAllGroupChats,
    BotCommandScopeAllPrivateChats,
    BotCommandScopeDefault,
)


def default_commands() -> List[BotCommand]:
    return [
        BotCommand(command="help", description="МЄШАНЯ 2.0: список команд"),
        BotCommand(command="ping", description="Перевірка бота"),
        BotCommand(command="id", description="Показати chat_id"),
        BotCommand(command="get", description="Скачати відео (YT/TikTok/IG)"),
        BotCommand(command="joke", description="Жарт (GPT/кастомний пул)"),
        BotCommand(command="roast", description="Підколоти @user"),
        BotCommand(command="rps", description="Камінь/ножиці/папір"),
        BotCommand(command="slot", description="Автомат"),
        BotCommand(command="chat_ai_on", description="AI-режим у чаті: ON"),
        BotCommand(command="chat_ai_off", description="AI-режим у чаті: OFF"),
        BotCommand(command="chat_ai_intensity", description="AI-інтенсивність 0-100"),
        BotCommand(command="chat_ai_status", description="Статус AI-режиму"),
        BotCommand(command="random_on", description="Рандомні вкиди: ON"),
        BotCommand(command="random_off", description="Рандомні вкиди: OFF"),
        BotCommand(command="random_window", description="Інтервал рандому (хв)"),
        BotCommand(command="mode", description="Тон жартів: pg13|r18"),
        BotCommand(command="quiet", description="Тихі години або off"),
        BotCommand(command="morning_on", description="Ранковий підйом ON"),
        BotCommand(command="morning_off", description="Ранковий підйом OFF"),
        BotCommand(command="morning_time", description="Час підйому (HH:MM)"),
        BotCommand(command="air_on_kyiv", description="Тривоги Київ — ON"),
        BotCommand(command="air_off_kyiv", description="Тривоги Київ — OFF"),
        BotCommand(command="air_on_region", description="Тривоги Область — ON"),
        BotCommand(command="air_off_region", description="Тривоги Область — OFF"),
        BotCommand(command="air_status", description="Поточний статус тривог"),
        BotCommand(command="air_districts", description="Райони Київщини та мої підписки"),
        BotCommand(command="air_district_on", description="Підписатися на район"),
        BotCommand(command="air_district_off", description="Відписатися від району"),
    ]


def admin_commands() -> List[BotCommand]:
    return [
        BotCommand(command="warn", description="Варн @user (3 = автомут 30хв)"),
        BotCommand(command="mute", description="М'ют @user [хв]"),
        BotCommand(command="unmute", description="Зняти м'ют @user"),
        BotCommand(command="ban", description="Бан @user"),
        BotCommand(command="kick", description="Кік @user"),
    ]


async def register_bot_commands(bot):
    await bot.set_my_commands(default_commands(), scope=BotCommandScopeDefault(), language_code="uk")
    await bot.set_my_commands(default_commands(), scope=BotCommandScopeAllPrivateChats(), language_code="uk")
    await bot.set_my_commands(default_commands(), scope=BotCommandScopeAllGroupChats(), language_code="uk")
    await bot.set_my_commands(admin_commands(), scope=BotCommandScopeAllChatAdministrators(), language_code="uk")


async def dump_commands_to_text(bot) -> str:
    scopes = [
        ("Default", BotCommandScopeDefault()),
        ("Privates", BotCommandScopeAllPrivateChats()),
        ("Groups", BotCommandScopeAllGroupChats()),
        ("Admins", BotCommandScopeAllChatAdministrators()),
    ]
    lines = []
    for name, scope in scopes:
        cmds = await bot.get_my_commands(scope=scope, language_code="uk")
        if not cmds:
            lines.append(f"[{name}] — немає команд")
            continue
        lines.append(f"[{name}]")
        for command in cmds:
            lines.append(f"/{command.command} — {command.description}")
        lines.append("")
    return "\n".join(lines).strip()
