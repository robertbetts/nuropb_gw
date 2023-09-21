import logging

import pytest
from tornado.web import Application, url

from nuropb_gw.handler_manager import HandlerManager
from nuropb_gw.handlers.ws_handler import WsHandler
from nuropb_gw.service_mesh_manager import ServiceMeshManagerController, ServiceMeshManager
logger = logging.getLogger()


@pytest.mark.asyncio
async def test_setup_ws_server(service_name, instance_id, amqp_url):
    """ The purpose of this test is to ensure that the websocket server can be instantiated
    """
    handler_manager = HandlerManager(
        service_name=service_name,
        instance_id=instance_id
    )
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
        # "authorise_from_token": authorise_from_token,
        "handler_manager": handler_manager,
        "service_mesh_manager": service_mesh_manager,
        "allowed_origins": ["*"],  # "*" allows all, rule is "ends_with" value in list ["localhost"],
    }
    application = Application(
        handlers=[
            url(r"/websocket", WsHandler, name="websocket_handler"),
        ],
        **application_settings,
    )
