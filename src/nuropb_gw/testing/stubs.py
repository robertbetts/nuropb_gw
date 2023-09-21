import logging
from typing import Any, Dict, Optional
from uuid import uuid4
import datetime

import tornado
from tornado.web import Application, url
from tornado.httpclient import HTTPRequest
from tornado.queues import QueueEmpty
from tornado.platform.asyncio import to_asyncio_future

from nuropb_gw.handler_manager import HandlerManager
from nuropb_gw.handlers.ws_handler import WsHandler
from nuropb_gw.service_mesh_manager import (
    ServiceMeshManager,
    ServiceMeshManagerController,
)

logger = logging.getLogger(__name__)
try:
    from faker import Faker

    faker = Faker()
except Exception as err:  # pragma: no cover
    _ = err
    logger.warning("Faker not installed, required for unit testing")
    faker = None


TEST_AUTH_TOKENS = ["accesstokentest1", "accesstokentest2", "accesstokentest3"]

_test_token_cache: Dict[str, Any] = {}
_test_user_id_cache: Dict[str, Any] = {}


def create_test_user_info(token: str) -> Dict[str, Any]:
    username = faker.email(safe=True)
    user_info = {
        "session_id": uuid4().hex,
        "last_activity": f"{datetime.datetime.now(datetime.timezone.utc).isoformat()}Z",
        "bearer_token": token,
        "user_id": username,
        "username": username,
        "kmsi": "0",
    }
    return user_info


def authorise_from_token(token) -> Optional[Dict[str, Any]]:
    if token not in TEST_AUTH_TOKENS:
        return None

    if token in _test_token_cache:
        return _test_token_cache[token]
    else:
        _test_token_cache[token] = create_test_user_info(token)
        _test_user_id_cache[_test_token_cache[token]["user_id"]] = _test_token_cache[
            token
        ]
        return _test_token_cache[token]


def websocket_server(service_name: str, instance_id: str, amqp_url: str) -> Application:
    handler_manager = HandlerManager(service_name=service_name, instance_id=instance_id)
    service_mesh_controller = ServiceMeshManagerController(
        service_name=service_name,
        instance_id=instance_id,
        event_topic_subscriptions=["hello"],
    )

    service_mesh_manager = ServiceMeshManager(
        service_name=service_name,
        instance_id=instance_id,
        handler_manager=handler_manager,
        amqp_url=amqp_url,
        service_controller=service_mesh_controller,
    )
    service_mesh_manager.connect()
    application_settings = {
        "xsrf_cookies": True,
        "session_cookie_name": "session",
        "cookie_secret": "cookie_secret",
        "allow_authorisation_cookie": True,
        "authentication_timeout": 15,
        "authorise_from_token": authorise_from_token,
        "handler_manager": handler_manager,
        "service_mesh_manager": service_mesh_manager,
        "allowed_origins": [
            "*"
        ],  # "*" allows all, rule is "ends_with" value in list ["localhost"],
    }

    application = Application(
        handlers=[
            url(r"/websocket", WsHandler, name="websocket_handler"),
        ],
        **application_settings,
    )
    return application


async def websocket_client(ws_url, headers=None, cookies=None):
    """Returns an asynchronous websocket client and instantiates a websocket server"""
    headers = {} if headers is None else headers
    cookies = {} if cookies is None else cookies
    params = {
        "url": ws_url,
        "headers": {
            "Authorization": "Bearer accesstokentest1",
        },
    }
    params["headers"].update(headers)

    return await tornado.websocket.websocket_connect(HTTPRequest(**params))


async def read_ws_message(conn) -> Any:
    try:
        msg = conn.read_queue.get_nowait()
    except QueueEmpty as e:
        _ = e
        msg = await to_asyncio_future(conn.read_message())
    return msg
