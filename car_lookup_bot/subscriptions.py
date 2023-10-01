from __future__ import annotations

import abc
import asyncio
import datetime
import logging
import secrets
import textwrap
from collections.abc import Iterable
from contextlib import suppress
from typing import Any

from aiogram import Bot
from pydantic import BaseModel, Field

from car_lookup_bot.car_info_readers import CarInfo, CarReader, RiaCarReader

logger = logging.getLogger(__name__)


class Subscription(BaseModel):
    id: str = Field(default_factory=lambda: secrets.token_hex(3))
    ria_url: str
    chat_id: int


class SubscriptionRepoABC(abc.ABC):
    @abc.abstractmethod
    async def add_subscription(self, subscription: Subscription) -> None:
        pass

    @abc.abstractmethod
    async def list_subscriptions(self) -> list[Subscription]:
        pass

    @abc.abstractmethod
    async def drop_subscription(self, subscription: Subscription) -> None:
        pass


class CarRepoABC(abc.ABC):
    @abc.abstractmethod
    async def add_car(self, car_info: CarInfo, subs_id: str) -> None:
        pass

    @abc.abstractmethod
    async def has_car(self, car_info: CarInfo, subs_id: str) -> bool:
        pass


class SubscriptionsService:
    def __init__(
        self,
        bot: Bot,
        subs_repo: SubscriptionRepoABC,
        car_repo: CarRepoABC,
        pooling_interval: datetime.timedelta = datetime.timedelta(minutes=1),
    ) -> None:
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._bot = bot
        self._subs_repo = subs_repo
        self._car_repo = car_repo
        self._pooling_interval = pooling_interval

    async def __aenter__(self) -> SubscriptionsService:
        old_subs = await self._subs_repo.list_subscriptions()
        for sub in old_subs:
            self._start_processing(sub)
        return self

    async def __aexit__(self, *args: Any) -> None:
        for task in self._tasks.values():
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

    async def add_subscription(self, sub: Subscription) -> None:
        logger.info(f"Adding new subscription {sub}")
        await self._subs_repo.add_subscription(sub)
        readers = [RiaCarReader(sub.ria_url)]
        await self._process_once(sub, readers, limit_send_cnt=3)
        self._start_processing(sub)

    async def list_subscriptions(self, chat_id: int) -> list[Subscription]:
        subs = await self._subs_repo.list_subscriptions()
        return [sub for sub in subs if sub.chat_id == chat_id]

    async def drop_subscription(self, subs: Subscription) -> None:
        await self._subs_repo.drop_subscription(subs)
        if task := self._tasks.pop(subs.id):
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

    def _start_processing(self, sub: Subscription) -> None:
        if sub.id in self._tasks:
            return
        self._tasks[sub.id] = asyncio.create_task(self._processor(sub))

    async def _processor(self, sub: Subscription) -> None:
        readers = [RiaCarReader(sub.ria_url)]
        while True:
            try:
                await self._process_once(sub, readers)
            except Exception:
                logging.exception("Failed to poll new cars")

            await asyncio.sleep(self._pooling_interval.total_seconds())

    async def _process_once(
        self,
        sub: Subscription,
        readers: Iterable[CarReader],
        limit_send_cnt: int | None = None,
    ) -> None:
        sent = 0
        for reader in readers:
            cars = await reader.read_cars()
            for car in cars:
                if await self._car_repo.has_car(car, sub.id):
                    continue
                if limit_send_cnt is None or sent < limit_send_cnt:
                    await self._send_notification(car, sub.chat_id)
                    logger.info(
                        f"Sending message to {sub.chat_id} about "
                        f"car {car.provider_car_id}"
                    )
                    sent += 1
                await self._car_repo.add_car(car, sub.id)

    async def _send_notification(self, car: CarInfo, chat_id: int) -> None:
        await self._bot.send_photo(
            chat_id=chat_id,
            photo=car.image_url,
            caption=textwrap.dedent(
                f"""\
                <b>{car.name}: {car.year}</b>
                Цена: {car.price_usd}$ {car.price_uah} грн
                Пробег: {car.mileage_km // 1000} тысяч км
                Добавлена в {car.add_time.strftime("%H:%M:%S %Y-%m-%d")}
                <a href="{car.link}">Детали</a>
                """
            ),
        )
