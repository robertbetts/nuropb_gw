import logging
import asyncio
from uuid import uuid4

import pytest_asyncio as pytest
import tornado
import tornado.httpserver
import tornado.testing
import tornado.httpclient
import tornado.websocket

from nuropb_gw.testing.stubs import gateway_server, websocket_client

logging.getLogger("faker.factory").setLevel(logging.WARNING)


@pytest.fixture(scope="session")
def amqp_url():
    return "amqp://guest:guest@localhost:5672/nuropb_gw_test"


@pytest.fixture(scope='function')
def unused_port():
    return tornado.testing.bind_unused_port()


@pytest.fixture(scope='session')
def service_name():
    return "test-ws-service"


@pytest.fixture(scope='function')
def instance_id():
    return uuid4().hex


@pytest.fixture(scope='function')
async def app(unused_port, amqp_url):
    return gateway_server(
        service_name="test-web-service",
        instance_id=uuid4().hex,
        amqp_url=amqp_url,
    )


@pytest.fixture(scope='function')
async def ws_server(unused_port, ws_app, amqp_url):
    server = tornado.httpserver.HTTPServer(ws_app)
    server.add_socket(unused_port[0])
    await asyncio.sleep(0)
    yield server

    server.stop()
    if hasattr(server, 'close_all_connections'):
        await server.close_all_connections()


@pytest.fixture(scope='function')
async def webserver(unused_port, app, amqp_url):
    server = tornado.httpserver.HTTPServer(app)
    server.add_socket(unused_port[0])
    await asyncio.sleep(0)
    yield server

    server.stop()
    if hasattr(server, 'close_all_connections'):
        await server.close_all_connections()


@pytest.fixture(scope='function')
def ws_url(webserver, unused_port):
    """Create an absolute base url (scheme://host:port)
    """
    return 'ws://localhost:%s/websocket' % unused_port[1]


@pytest.fixture(scope='function')
async def ws_conn(webserver, ws_url):
    """Returns an asynchronous websocket client and instantiates a websocket server
    """
    headers = {
        "Authorization": "Bearer accesstokentest1",
    }
    return await websocket_client(ws_url, headers=headers)


@pytest.fixture(scope='function')
def web_url(webserver, unused_port):
    """Create an absolute base url (scheme://host:port)
    """
    return 'http://localhost:%s/' % unused_port[1]


@pytest.fixture(scope='function')
def web_url_private(webserver, unused_port):
    """Create an absolute base url (scheme://host:port)
    """
    return 'http://localhost:%s/private' % unused_port[1]


@pytest.fixture(scope='function')
def web_client(webserver):
    """Get an asynchronous HTTPS client.
    """
    # How does on get ca_certs from the user
    return tornado.httpclient.AsyncHTTPClient()