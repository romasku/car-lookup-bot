from car_lookup_bot.car_info_readers import CarInfo
from car_lookup_bot.subscriptions import CarRepoABC


class InMemoryCarRepo(CarRepoABC):
    def __init__(self) -> None:
        self.cars_ids: set[tuple[str, str]] = set()

    async def add_car(self, car_info: CarInfo) -> None:
        self.cars_ids.add((car_info.provider_name, car_info.provider_car_id))

    async def has_car(self, car_info: CarInfo) -> bool:
        return (car_info.provider_name, car_info.provider_car_id) in self.cars_ids
