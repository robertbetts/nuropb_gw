import logging
import asyncio
from uuid import uuid4

from nuropb.rmq_api import RMQAPI
from nuropb.rmq_lib import configure_nuropb_rmq, create_virtual_host

logger = logging.getLogger(__name__)


amqp_url = "amqp://guest:guest@localhost:5672/nuropb_gw_test"
rmq_api_url = "http://guest:guest@localhost:15672/api"


class MeshServiceInstance:
    _service_name = "mesh-service"
    _instance_id = uuid4().hex


async def main():
    test_instance = MeshServiceInstance()
    api = RMQAPI(
        amqp_url=amqp_url,
        service_name=test_instance._service_name,
        instance_id=test_instance._instance_id,
        service_instance=test_instance,
    )
    create_virtual_host(rmq_api_url, amqp_url)
    transport_settings = api.transport.rmq_configuration
    configure_nuropb_rmq(
        service_name=test_instance._service_name,
        rmq_url=amqp_url,
        events_exchange=transport_settings["events_exchange"],
        rpc_exchange=transport_settings["rpc_exchange"],
        dl_exchange=transport_settings["dl_exchange"],
        dl_queue=transport_settings["dl_queue"],
        service_queue=transport_settings["service_queue"],
        rpc_bindings=transport_settings["rpc_bindings"],
        event_bindings=transport_settings["event_bindings"],
    )


if __name__ == "__main__":
    log_format = (
        "%(levelname) -10s %(asctime)s %(name) -30s %(funcName) "
        "-35s %(lineno) -5d: %(message)s"
    )
    logging.basicConfig(level=logging.INFO, format=log_format)
    logging.getLogger("pika").setLevel(logging.WARNING)
    logging.getLogger("nuropb").setLevel(logging.WARNING)
    asyncio.run(main())



