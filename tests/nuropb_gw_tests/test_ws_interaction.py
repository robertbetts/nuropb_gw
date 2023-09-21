import json
import secrets
from typing import Dict, Any
import logging
import asyncio

import pytest

from nuropb_gw.testing.stubs import websocket_client, read_ws_message

logger = logging.getLogger()


@pytest.mark.asyncio
async def test_websocket_register_hello(ws_url) -> None:
    headers = {
        "Authorization": "Bearer :" + "accesstokentest1"
    }
    conn = await websocket_client(ws_url, headers=headers)
    assert conn is not None
    msg = await read_ws_message(conn)
    message = json.loads(msg)
    assert message["type"] == "event"
    assert message["payload"]["topic"] == "hello"
    assert msg is not None


@pytest.mark.asyncio
async def test_multi_websocket_interaction(ws_url, app) -> None:
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
    await asyncio.sleep(0)
    handler_manager = app.settings["handler_manager"]
    handler = handler_manager.get_handler(session_id1)
    assert handler is not None

    def make_test_event(code: str) -> Dict[str, Any]:
        return {
            "type": "event",
            "payload": {
                "topic": "test-event",
                "event": {
                    "test_code": code,
                },
            }
        }

    test_code = secrets.token_hex(8)
    test_event = make_test_event(test_code)
    await handler.write_message(test_event)
    msg = await read_ws_message(conn1)
    message = json.loads(msg)
    assert message["payload"]["event"]["test_code"] == test_code

    await handler_manager.send_message(session_id1, test_event)
    msg = await read_ws_message(conn1)
    message = json.loads(msg)
    assert message["payload"]["event"]["test_code"] == test_code

    """ Send to all with only one connection
    """
    test_code = secrets.token_hex(8)
    test_event = make_test_event(test_code)
    logger.info(f"send test event to all with code: {test_code}")
    await handler_manager.send_message_to_all(test_event)
    msg = await read_ws_message(conn1)
    message = json.loads(msg)
    assert message["payload"]["event"]["test_code"] == test_code

    """ Connect a new user with their first connection
    """
    headers = {
        "Authorization": "Bearer :" + "accesstokentest2"
    }
    conn2 = await websocket_client(ws_url, headers=headers)
    assert conn2 is not None
    msg = await read_ws_message(conn2)
    message = json.loads(msg)
    session_id2 = message["payload"]["event"]["session_id"]
    user_id2 = message["payload"]["event"]["user_id"]

    """ Send to all with only two different user_id connections
    """
    test_code = secrets.token_hex(8)
    test_event = make_test_event(test_code)
    logger.info(f"send test event to all with code: {test_code}")
    await handler_manager.send_message_to_all(test_event)
    msg = await read_ws_message(conn1)
    message = json.loads(msg)
    assert message["payload"]["event"]["test_code"] == test_code
    msg = await read_ws_message(conn2)
    message = json.loads(msg)
    assert message["payload"]["event"]["test_code"] == test_code

    """ Connect an existing user with a second connection
    """
    headers = {
        "Authorization": "Bearer :" + "accesstokentest1"
    }
    conn3 = await websocket_client(ws_url, headers=headers)
    msg = await read_ws_message(conn3)
    message = json.loads(msg)
    assert conn3 is not None
    session_id3 = message["payload"]["event"]["session_id"]
    user_id3 = message["payload"]["event"]["user_id"]

    """ Sending message one user, each with two connection (three connections exits across two users)
    """
    test_code1 = secrets.token_hex(8)
    test_event = make_test_event(test_code1)
    await handler_manager.send_message_to_user_ids([user_id1, user_id3], test_event)

    """ Sending message one user, each with one connection (three connections exits across two users)
    """
    test_code2 = secrets.token_hex(8)
    test_event = make_test_event(test_code2)
    await handler_manager.send_message_to_user_ids([user_id2], test_event)

    msg = await read_ws_message(conn1)
    message = json.loads(msg)
    assert message["payload"]["event"]["test_code"] == test_code1

    msg = await read_ws_message(conn2)
    message = json.loads(msg)
    assert message["payload"]["event"]["test_code"] == test_code2

    msg = await read_ws_message(conn3)
    message = json.loads(msg)
    assert message["payload"]["event"]["test_code"] == test_code1

    handler_manager.close(session_id1)
    await asyncio.sleep(0.1)  # Allow handler to react
    assert handler_manager.get_handler(session_id1) is None

    handler_manager.close_user_ids([user_id2, user_id3])
    await asyncio.sleep(0.1)  # Allow handlers to react
    assert len(handler_manager._session_id_to_handler) == 0
    assert len(handler_manager._user_id_to_session_ids) == 0

    headers = {
        "Authorization": "Bearer :" + "accesstokentest2"
    }
    conn4 = await websocket_client(ws_url, headers=headers)
    msg = await read_ws_message(conn4)
    message = json.loads(msg)
    headers = {
        "Authorization": "Bearer :" + "accesstokentest1"
    }
    conn5 = await websocket_client(ws_url, headers=headers)
    msg = await read_ws_message(conn5)
    message = json.loads(msg)
    headers = {
        "Authorization": "Bearer :" + "accesstokentest1"
    }
    conn6 = await websocket_client(ws_url, headers=headers)
    msg = await read_ws_message(conn6)
    message = json.loads(msg)
    headers = {
        "Authorization": "Bearer :" + "accesstokentest3"
    }
    conn7 = await websocket_client(ws_url, headers=headers)
    msg = await read_ws_message(conn7)
    message = json.loads(msg)

    assert len(handler_manager._user_id_to_session_ids) == 3
    handler_manager.close_all()
    await asyncio.sleep(0.01)  # Allow handlers to react
    assert len(handler_manager._session_id_to_handler) == 0
    assert len(handler_manager._user_id_to_session_ids) == 0

    headers = {
        "Authorization": "Bearer :" + "accesstokentest44"
    }
    conn8 = await websocket_client(ws_url, headers=headers)
    assert conn8 is not None
