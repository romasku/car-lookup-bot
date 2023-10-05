import datetime
from typing import Any

import httpx
from httpx import Cookies
from pydantic import BaseModel


class TickerReaderConf(BaseModel):
    identity: str
    csrf: str
    webchsid2: str
    csrf_header: str
    office_id: str
    date: datetime.date


def setup_client(conf: TickerReaderConf) -> httpx.AsyncClient:
    jar = Cookies()
    jar.set(name="_identity", value=conf.identity, domain="eq.hsc.gov.ua")
    jar.set(name="_csrf", value=conf.csrf, domain="eq.hsc.gov.ua")
    jar.set(name="WEBCHSID2", value=conf.webchsid2, domain="eq.hsc.gov.ua")

    headers = {
        "accept": "*/*",
        "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Host": "eq.hsc.gov.ua",
        "Origin": "https://eq.hsc.gov.ua",
        "Referer": "https://eq.hsc.gov.ua/site/step2?chdate=2023-10-10&question_id=56&id_es=",  # noqa
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "x-requested-with": "XMLHttpRequest",
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36",  # noqa
        "sec-ch-ua": '"Google Chrome";v="117", "Not;A=Brand";v="8", "Chromium";v="117"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Linux"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "X-Csrf-Token": conf.csrf_header,
    }
    return httpx.AsyncClient(verify=False, cookies=jar, headers=headers)


class Ticket(BaseModel):
    id: str
    office_id: str
    time: datetime.datetime


class TicketReader:
    def __init__(self, conf: TickerReaderConf) -> None:
        self._client = setup_client(conf)
        self._conf = conf

    async def __aenter__(self) -> "TicketReader":
        return self

    async def __aexit__(self, *args: Any) -> None:
        print("WEBCHSID2: ", self._client.cookies.get("WEBCHSID2"))

    def get_current_webchsid2(self) -> str:
        return self._client.cookies.get("WEBCHSID2") or ""

    async def get_tickets(self) -> list[Ticket]:
        resp = await self._client.post(
            "https://eq.hsc.gov.ua/site/freetimes",
            content=f"office_id={self._conf.office_id}&date_of_admission={self._conf.date.strftime('%Y-%m-%d')}&question_id=56&es_date=&es_time=",  # noqa
        )
        resp.raise_for_status()
        data = resp.json()
        res: list[Ticket] = []
        for row in data["rows"]:
            res.append(
                Ticket(
                    id=str(row["id"]),
                    time=datetime.datetime.combine(
                        self._conf.date,
                        datetime.datetime.strptime(row["chtime"], "%H:%M").time(),
                    ),
                    office_id=self._conf.office_id,
                )
            )
        return res
