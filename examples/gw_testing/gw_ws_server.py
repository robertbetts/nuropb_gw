import logging
import asyncio
from uuid import uuid4

import tornado
import tornado.httpserver
import tornado.testing
import tornado.httpclient
import tornado.websocket

from nuropb_gw.testing.stubs import gateway_server

logger = logging.getLogger(__name__)


amqp_url = "amqp://guest:guest@localhost:5672/nuropb_gw_test"
websocket_port = 9080


async def main():
    app = gateway_server(
        service_name="test-ws-service",
        instance_id=uuid4().hex,
        amqp_url=amqp_url,
    )

    server = tornado.httpserver.HTTPServer(app)
    server.listen(websocket_port, reuse_port=True)
    await asyncio.sleep(1)

    smm = app.settings["service_mesh_manager"]
    if not smm.connected:
        logger.info("service mesh manager not connected to the service mesh, exiting test")
        server.stop()
        return

    try:
        await asyncio.Event().wait()
        logger.info("Shutting down")
    except BaseException as err:
        logger.info("Shutting down. %s: %a", type(err).__name__, str(err))

    smm.disconnect()
    await asyncio.sleep(0.1)
    server.stop()
    if hasattr(server, 'close_all_connections'):
        await server.close_all_connections()


if __name__ == "__main__":
    log_format = (
        "%(levelname) -10s %(asctime)s %(name) -30s %(funcName) "
        "-35s %(lineno) -5d: %(message)s"
    )
    logging.basicConfig(level=logging.CRITICAL, format=log_format)
    logging.getLogger("pika").setLevel(logging.WARNING)
    logging.getLogger("nuropb").setLevel(logging.INFO)
    logging.getLogger("nuropb_gw").setLevel(logging.INFO)
    asyncio.run(main())
