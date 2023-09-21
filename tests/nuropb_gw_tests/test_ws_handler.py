import logging
import json

import pytest

from nuropb_gw.testing.stubs import websocket_client

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def test_open_ws_connection(ws_url):
    ws_conn = await websocket_client(ws_url, headers={}, cookies={})
    json_message = await ws_conn.read_ws_message()
    message = json.loads(json_message)
    logger.debug(message)
    assert isinstance(message, dict)
    assert message["type"] == "event"
    assert message["payload"]["topic"] == "hello"


@pytest.mark.asyncio
async def test_open_ws_connection(ws_conn):
    json_message = await ws_conn.read_message()
    message = json.loads(json_message)
    logger.debug(message)
    assert isinstance(message, dict)
    assert message["type"] == "event"
    assert message["payload"]["topic"] == "hello"
