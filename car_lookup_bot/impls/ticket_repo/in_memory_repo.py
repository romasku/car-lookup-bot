from car_lookup_bot.exam_tickets import Ticket
from car_lookup_bot.subscriptions import TicketRepoABC


class InMemoryTicketRepo(TicketRepoABC):
    def __init__(self) -> None:
        self.cars_ids: set[tuple[str, str]] = set()

    async def add_ticket(self, ticket: Ticket, subs_id: str) -> None:
        self.cars_ids.add((ticket.id, subs_id))

    async def has_ticket(self, ticket: Ticket, subs_id: str) -> bool:
        return (ticket.id, subs_id) in self.cars_ids
