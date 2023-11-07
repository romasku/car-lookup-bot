import asyncio
import datetime
import logging
import sys
import textwrap

from aiogram import Bot, Dispatcher, Router, types
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import Message
from pydantic import BaseModel
from redis.asyncio.client import Redis

from car_lookup_bot.car_info_readers import RiaCarReader
from car_lookup_bot.exam_tickets import TickerReaderConf, TicketReader
from car_lookup_bot.impls.car_repo.redis_repo import RedisCarRepo
from car_lookup_bot.impls.subs_repo.redis_repo import RedisSubscriptionRepo
from car_lookup_bot.impls.ticket_repo.redis_repo import RedisTicketRepo
from car_lookup_bot.settings import Settings
from car_lookup_bot.subscriptions import (
    CarSubscription,
    Subscription,
    SubscriptionsService,
    TicketSubscription,
)

TOKEN = "6569853340:AAGF-aPdFyKK1ZkJuJ8ysjciKBkfANqdXHg"
# TOKEN = "6471025208:AAEr4GcALPGey1Ws5Jg3yx9Ovi8Ju--n0tM"  # Local token

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
        /subscribe_ticket yyyy-mm-dd office_id tokens_json -\
 начать слежку за талонами на экзамен. Туполева - office_id=142
        /subscriptions - получить список активных подписок
        /unsubscribe subscription_id - отменить подписку
        """
        )
    )


@router.message(Command("subscribe"))
async def command_subscribe(
    message: types.Message, command: CommandObject, subs_service: SubscriptionsService
) -> None:
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
    sub = CarSubscription(
        ria_url=url,
        chat_id=message.chat.id,
    )
    await message.answer(
        f"Подписка {sub.id} на обновления создана, вот последние 3 машины:"
    )
    await subs_service.add_subscription(sub)


class TicketSubsTokens(BaseModel):
    identity: str
    csrf: str
    webchsid2: str
    csrf_header: str


@router.message(Command("subscribe_ticket"))
async def command_subscribe_ticket(
    message: types.Message, command: CommandObject, subs_service: SubscriptionsService
) -> None:
    if command.args is None:
        await message.answer(f"Нужно указать дату")
        return

    args = command.args.split(" ", maxsplit=3)
    print(args)

    if len(args) == 4:
        date_start_str, date_end_str, office_id, tokens_raw = args
    else:
        await message.answer(f"Неправильное кол-во параметров")
        return

    try:
        date_start = datetime.datetime.strptime(date_start_str, "%Y-%m-%d")
        date_end = datetime.datetime.strptime(date_end_str, "%Y-%m-%d")
    except Exception:
        await message.answer(
            f"Неправильная дата. Формат yyyy-mm-dd, например 2023-10-10"
        )
        return
    try:
        tokens = TicketSubsTokens.model_validate_json(tokens_raw)
    except Exception as e:
        print(e)
        await message.answer(f"Неправильные токены")
        return

    conf = TickerReaderConf(
        identity=tokens.identity,
        csrf=tokens.csrf,
        csrf_header=tokens.csrf_header,
        webchsid2=tokens.webchsid2,
        office_id=office_id,
        date_start=date_start,
        date_end=date_end,
    )

    try:
        async with TicketReader(conf) as reader:
            await reader._get_tickets(date_start)
            conf.webchsid2 = reader.get_current_webchsid2()
    except Exception:
        await message.answer(f"Ошибка при загрузке результатов. Токены рабочие?")
        return

    sub = TicketSubscription(
        conf=conf,
        chat_id=message.chat.id,
    )
    await message.answer(f"Подписка {sub.id} на талоны создана.")
    await subs_service.add_subscription(sub)


def _make_sub_desc(sub: Subscription) -> str:
    res = f"Подписка {sub.id}"
    if isinstance(sub, CarSubscription):
        res += f" на {sub.ria_url}"
    if isinstance(sub, TicketSubscription):
        res += f" на талоны на {sub.conf.date_start}-{sub.conf.date_end}"
    if sub.last_update is not None:
        res += f" (последние обновление {sub.last_update.strftime('%H:%M:%S')})"
    return res


@router.message(Command("subscriptions"))
async def command_subscriptions(
    message: types.Message, subs_service: SubscriptionsService
) -> None:
    subs = await subs_service.list_subscriptions(message.chat.id)
    if len(subs) == 0:
        await message.answer("У вас пока что нет подписок")
    else:
        await message.answer("\n".join([_make_sub_desc(sub) for sub in subs]))


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
            await message.answer(f"{_make_sub_desc(sub)} удалена")
            if isinstance(sub, TicketSubscription):
                await message.answer(f"Актуальный webchsid2 {sub.conf.webchsid2}")
            return
    else:
        await message.answer(f"Подписка {sub_id} нe найдена")


async def async_main() -> None:
    settings = Settings()

    bot = Bot(TOKEN, parse_mode=ParseMode.HTML)

    redis_client = Redis.from_url(settings.REDIS_URL)
    car_repo = RedisCarRepo(redis_client)
    ticket_repo = RedisTicketRepo(redis_client)
    subs_repo = RedisSubscriptionRepo(redis_client)
    async with SubscriptionsService(
        bot=bot, subs_repo=subs_repo, car_repo=car_repo, ticket_repo=ticket_repo
    ) as subs_service:
        dp = Dispatcher(subs_service=subs_service)
        dp.include_router(router)
        await dp.start_polling(bot)


def main() -> None:
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
