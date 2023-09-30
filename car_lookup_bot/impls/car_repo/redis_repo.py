from redis.asyncio import Redis

from car_lookup_bot.car_info_readers import CarInfo
from car_lookup_bot.subscriptions import CarRepoABC


class RedisCarRepo(CarRepoABC):
    def __init__(
        self,
        client: Redis,
    ) -> None:
        self._client = client
        self._key = "cars"

    async def add_car(self, car_info: CarInfo, subs_id: str) -> None:
        await self._client.sadd("cars", self._car_to_id(car_info, subs_id))

    async def has_car(self, car_info: CarInfo, subs_id: str) -> bool:
        return await self._client.sismember("cars", self._car_to_id(car_info, subs_id))

    def _car_to_id(self, car_info: CarInfo, subs_id: str) -> bytes:
        return (
            car_info.provider_name + "|" + car_info.provider_car_id + "|" + subs_id
        ).encode()
