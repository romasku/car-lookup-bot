from redis.asyncio import Redis

from car_lookup_bot.exam_tickets import Ticket
from car_lookup_bot.subscriptions import TicketRepoABC


class RedisTicketRepo(TicketRepoABC):
    def __init__(
        self,
        client: Redis,
    ) -> None:
        self._client = client
        self._key = "tickets"

    async def add_ticket(self, ticket: Ticket, subs_id: str) -> None:
        await self._client.sadd("tickets", self._ticket_to_id(ticket, subs_id))

    async def has_ticket(self, ticket: Ticket, subs_id: str) -> bool:
        return await self._client.sismember(
            "tickets", self._ticket_to_id(ticket, subs_id)
        )

    def _ticket_to_id(self, ticket: Ticket, subs_id: str) -> bytes:
        return (ticket.id + "|" + subs_id).encode()
