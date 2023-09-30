from __future__ import annotations

import asyncio
from collections.abc import Iterator
from typing import Any

import pytest


@pytest.fixture(scope="session")
def event_loop(request: Any) -> Iterator[asyncio.AbstractEventLoop]:
    """Create an instance of the default event loop for tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()
