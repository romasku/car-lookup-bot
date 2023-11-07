from __future__ import annotations

import asyncio
import datetime
import logging
from collections.abc import AsyncIterator
from typing import Any

import httpx
from httpx import Cookies
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class TickerReaderConf(BaseModel):
    identity: str
    csrf: str
    webchsid2: str
    csrf_header: str
    office_id: str
    date_start: datetime.date
    date_end: datetime.date
    pause_between_requests: datetime.timedelta = datetime.timedelta(seconds=1)


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

    async def __aenter__(self) -> TicketReader:
        return self

    async def __aexit__(self, *args: Any) -> None:
        print("WEBCHSID2: ", self._client.cookies.get("WEBCHSID2"))

    def get_current_webchsid2(self) -> str:
        return self._client.cookies.get("WEBCHSID2") or ""

    async def get_tickets(self) -> AsyncIterator[Ticket]:
        day_cnt = (self._conf.date_end - self._conf.date_start).days + 1
        for day_idx in range(day_cnt):
            res = await self._get_tickets(
                self._conf.date_start + datetime.timedelta(days=day_idx)
            )
            for ticket in res:
                yield ticket
            await asyncio.sleep(self._conf.pause_between_requests.total_seconds())

    async def _get_tickets(self, date: datetime.date) -> list[Ticket]:
        logger.info(f"Requesting tickets for date {date}")
        resp = await self._client.post(
            "https://eq.hsc.gov.ua/site/freetimes",
            content=f"office_id={self._conf.office_id}"
            f"&date_of_admission={date.strftime('%Y-%m-%d')}"
            f"&question_id=55&es_date=&es_time=",
        )
        resp.raise_for_status()
        data = resp.json()
        res: list[Ticket] = []
        for row in data["rows"]:
            res.append(
                Ticket(
                    id=str(row["id"]),
                    time=datetime.datetime.combine(
                        date,
                        datetime.datetime.strptime(row["chtime"], "%H:%M").time(),
                    ),
                    office_id=self._conf.office_id,
                )
            )
        return res
