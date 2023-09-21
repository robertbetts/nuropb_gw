import json
import logging
import asyncio

import pytest

from nuropb_gw.testing.stubs import websocket_client, read_ws_message

logger = logging.getLogger()


@pytest.mark.asyncio
async def test_ws_connect_and_close(ws_url, app) -> None:
    headers = {
        "Authorization": "Bearer :" + "accesstokentest1"
    }
    conn1 = await websocket_client(ws_url, headers=headers)
    assert conn1 is not None
    msg = await read_ws_message(conn1)
    message = json.loads(msg)
    assert message["type"] == "event"
    assert message["payload"]["topic"] == "hello"
    session_id1 = message["payload"]["event"]["session_id"]
    user_id1 = message["payload"]["event"]["user_id"]
    assert msg is not None

    handler_manager = app.settings["handler_manager"]
    handler = handler_manager.get_handler(session_id1)
    assert handler is not None

    handler_manager.close(session_id1)
    await asyncio.sleep(0.2)

    handler = handler_manager.get_handler(session_id1)
    assert handler is None

    headers = {
        "Authorization": "Bearer :" + "accesstokentest1"
    }
    conn1 = await websocket_client(ws_url, headers=headers)
    assert conn1 is not None
    msg = await read_ws_message(conn1)
    message = json.loads(msg)
    user_id1 == message["payload"]["event"]["user_id"]

    conn2 = await websocket_client(ws_url, headers=headers)
    assert conn2 is not None
    msg = await read_ws_message(conn2)
    message = json.loads(msg)
    assert user_id1 == message["payload"]["event"]["user_id"]

    headers = {
        "Authorization": "Bearer :" + "accesstokentest2"
    }
    conn3 = await websocket_client(ws_url, headers=headers)
    assert conn3 is not None
    msg = await read_ws_message(conn3)
    message = json.loads(msg)
    user_id3 = message["payload"]["event"]["user_id"]
    handler_manager.close_user_ids([user_id1, user_id3])
    await asyncio.sleep(0.1)
    assert len(handler_manager._user_id_to_session_ids) == 0

    headers = {
        "Authorization": "Bearer :" + "accesstokentest1"
    }
    conn1 = await websocket_client(ws_url, headers=headers)
    assert conn1 is not None
    msg = await read_ws_message(conn1)
    message = json.loads(msg)
    user_id1 == message["payload"]["event"]["user_id"]

    conn2 = await websocket_client(ws_url, headers=headers)
    assert conn2 is not None
    msg = await read_ws_message(conn2)
    message = json.loads(msg)
    assert user_id1 == message["payload"]["event"]["user_id"]

    handler_manager.close_all()
    await asyncio.sleep(0.1)
    assert len(handler_manager._user_id_to_session_ids) == 0

@pytest.mark.asyncio
async def test_manager_received_bad_json(ws_url, app) -> None:
    headers = {
        "Authorization": "Bearer :" + "accesstokentest1"
    }
    conn = await websocket_client(ws_url, headers=headers)
    assert conn is not None
    msg = await read_ws_message(conn)
    message = json.loads(msg)
    # session_id1 = message["payload"]["event"]["session_id"]
    # user_id1 = message["payload"]["event"]["user_id"]
    assert msg is not None
    conn.write_message("{'key': 'bad json'")
    asyncio.sleep(0.1)
    assert len(app.settings["handler_manager"]._session_id_to_handler) == 1
    msg = await read_ws_message(conn)
    message = json.loads(msg)
    assert message["description"].startswith("Error decoding JSON")

