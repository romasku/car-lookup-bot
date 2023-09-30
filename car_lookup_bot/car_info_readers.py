import abc
import datetime
import logging

from bs4 import BeautifulSoup, Tag
from httpx import AsyncClient
from pydantic import BaseModel


class CarInfo(BaseModel):
    provider_name: str
    provider_car_id: str

    name: str
    year: int
    price_usd: int
    price_uah: int
    mileage_km: int
    add_time: datetime.datetime
    image_url: str
    link: str


class CarReader(abc.ABC):
    @abc.abstractmethod
    async def read_cars(self) -> list[CarInfo]:
        pass


class RiaCarReader(CarReader):
    def __init__(self, url: str) -> None:
        self._url = url
        self._client = AsyncClient()

    async def read_cars(self) -> list[CarInfo]:
        res: list[CarInfo] = []
        resp = await self._client.get(self._url)
        bs = BeautifulSoup(resp.read(), features="html.parser")
        sr = bs.find(id="searchResults")
        if not isinstance(sr, Tag):
            logging.warning("Failed to parse AutoRia response")
            return []
        for tag in sr.children:
            if not isinstance(tag, Tag) or tag.name != "section":
                continue
            name_tag = tag.find(class_="ticket-title")
            if name_tag is None:
                continue
            name, year = name_tag.text.strip().rsplit(" ", 1)
            price_tag = tag.find(class_="price-ticket")
            assert isinstance(price_tag, Tag)
            price_usd = price_tag.find(  # type: ignore
                "span", attrs={"data-currency": "USD"}
            ).text
            price_uah = price_tag.find(  # type: ignore
                "span", attrs={"data-currency": "UAH"}
            ).text

            mileage_tag = tag.find(class_="js-race")
            assert isinstance(mileage_tag, Tag)
            mileage_km = int(mileage_tag.text.split(" ")[1]) * 1000

            time_tag = tag.find(attrs={"data-add-date": True})
            assert isinstance(time_tag, Tag)
            add_time_raw = time_tag.attrs["data-add-date"]
            add_time = datetime.datetime.strptime(add_time_raw, "%Y-%m-%d %H:%M:%S")

            img_tag = tag.find("img")
            assert isinstance(img_tag, Tag)
            image_url = img_tag.attrs["src"]

            link_tag = tag.find(class_="m-link-ticket")
            assert isinstance(link_tag, Tag)
            link = link_tag.attrs["href"]

            info = CarInfo(
                provider_name="ria",
                provider_car_id=tag.attrs["data-advertisement-id"],
                name=name.strip(),
                year=int(year),
                price_usd=int(price_usd.replace(" ", "")),
                price_uah=int(price_uah.replace(" ", "")),
                mileage_km=mileage_km,
                add_time=add_time,
                image_url=image_url,
                link=link,
            )
            res.append(info)
        return res
