import asyncio
import logging
import sys
import textwrap

from aiogram import Bot, Dispatcher, Router, types
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import Message
from redis.asyncio.client import Redis

from car_lookup_bot.car_info_readers import RiaCarReader
from car_lookup_bot.impls.car_repo.redis_repo import RedisCarRepo
from car_lookup_bot.impls.subs_repo.redis_repo import RedisSubscriptionRepo
from car_lookup_bot.settings import Settings
from car_lookup_bot.subscriptions import Subscription, SubscriptionsService

TOKEN = "6569853340:AAGF-aPdFyKK1ZkJuJ8ysjciKBkfANqdXHg"

# All handlers should be attached to the Router (or Dispatcher)


router = Router()


@router.message(CommandStart())
async def command_start_handler(message: Message) -> None:
    """
    This handler receives messages with `/start` command
    """
    await message.answer(
        textwrap.dedent(
            """\
        Привет! Это бот для поиска машины. Поддерживаемые комманды:
        /subscribe ria_url - начать слежку за обявлениями по ссылке
        /subscriptions - получить список активных подписок
        /unsubscribe subscription_id - отменить подписку
        """
        )
    )


@router.message(Command("subscribe"))
async def command_subscribe(
    message: types.Message, command: CommandObject, subs_service: SubscriptionsService
) -> None:
    """
    This handler receives messages with `/start` command
    """
    url = command.args
    if url is None:
        await message.answer(f"Нужно указать ссылку на риа поиск")
        return
    try:
        await RiaCarReader(url).read_cars()
    except Exception:
        await message.answer(
            f"Ошибка при загрузке резальтатов по ссылке. Ссылка правильная?"
        )
        return
    sub = Subscription(
        ria_url=url,
        chat_id=message.chat.id,
    )
    await message.answer(
        f"Подписка {sub.id} на обновления создана, вот последние 3 машины:"
    )
    await subs_service.add_subscription(sub)


@router.message(Command("subscriptions"))
async def command_subscriptions(
    message: types.Message, subs_service: SubscriptionsService
) -> None:
    subs = await subs_service.list_subscriptions(message.chat.id)
    if len(subs) == 0:
        await message.answer("У вас пока что нет подписок")
    else:
        await message.answer(
            "\n".join([f"Подписка {sub.id} на {sub.ria_url}" for sub in subs])
        )


@router.message(Command("unsubscribe"))
async def command_unsubscribe(
    message: types.Message, command: CommandObject, subs_service: SubscriptionsService
) -> None:
    sub_id = command.args
    if sub_id is None:
        await message.answer(f"Нужно указать айди подписки")
        return
    subs = await subs_service.list_subscriptions(message.chat.id)
    for sub in subs:
        if sub.id == sub_id:
            await subs_service.drop_subscription(sub)
            await message.answer(f"Подписка {sub.id} на {sub.ria_url} удалена")
            return
    else:
        await message.answer(f"Подписка {sub_id} нe найдена")


async def async_main() -> None:
    settings = Settings()

    bot = Bot(TOKEN, parse_mode=ParseMode.HTML)

    redis_client = Redis.from_url(settings.REDIS_URL)
    car_repo = RedisCarRepo(redis_client)
    subs_repo = RedisSubscriptionRepo(redis_client)
    async with SubscriptionsService(
        bot=bot, subs_repo=subs_repo, car_repo=car_repo
    ) as subs_service:
        dp = Dispatcher(subs_service=subs_service)
        dp.include_router(router)
        await dp.start_polling(bot)


def main() -> None:
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
