from redis.asyncio import Redis

from car_lookup_bot.subscriptions import (
    CarSubscription,
    Subscription,
    SubscriptionRepoABC,
    TicketSubscription,
)


class RedisSubscriptionRepo(SubscriptionRepoABC):
    def __init__(
        self,
        client: Redis,
    ) -> None:
        self._client = client

    async def add_subscription(self, subscription: Subscription) -> None:
        key = f"subscriptions"
        await self._client.sadd(key, self._dump_sub(subscription))

    async def list_subscriptions(self) -> list[Subscription]:
        key = f"subscriptions"
        res: list[Subscription] = []
        async for entry in self._client.sscan_iter(key):
            res.append(self._load_sub(entry))
        return res

    async def update_subscription(self, subscription: Subscription) -> None:
        subs = await self.list_subscriptions()
        for sub in subs:
            if sub.id == subscription.id:
                await self.drop_subscription(sub)
        await self.add_subscription(subscription)

    async def drop_subscription(self, subscription: Subscription) -> None:
        key = f"subscriptions"
        await self._client.srem(key, self._dump_sub(subscription))

    def _dump_sub(self, sub: Subscription) -> bytes:
        return sub.model_dump_json(by_alias=True).encode()

    def _load_sub(self, raw_data: bytes) -> Subscription:
        try:
            return CarSubscription.model_validate_json(raw_data)
        except ValueError:
            return TicketSubscription.model_validate_json(raw_data)
