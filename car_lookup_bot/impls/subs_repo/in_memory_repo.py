from car_lookup_bot.subscriptions import Subscription, SubscriptionRepoABC


class InMemoryAuctionRepo(SubscriptionRepoABC):
    def __init__(self) -> None:
        self.subs: dict[str, Subscription] = {}

    async def add_subscription(self, subscription: Subscription) -> None:
        self.subs[subscription.id] = subscription

    async def update_subscription(self, subscription: Subscription) -> None:
        self.subs[subscription.id] = subscription

    async def list_subscriptions(self) -> list[Subscription]:
        return list(self.subs.values())

    async def drop_subscription(self, subscription: Subscription) -> None:
        self.subs.pop(subscription.id, None)
