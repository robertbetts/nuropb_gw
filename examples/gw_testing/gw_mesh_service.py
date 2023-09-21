import logging
import asyncio
from uuid import uuid4

from nuropb.contexts.context_manager_decorator import nuropb_context
from nuropb.contexts.describe import publish_to_mesh
from nuropb.rmq_api import RMQAPI

logger = logging.getLogger(__name__)

amqp_url = "amqp://guest:guest@localhost:5672/nuropb_gw_test"


class MeshServiceInstance:
    _service_name = "mesh-test"
    _instance_id = uuid4().hex

    @nuropb_context
    @publish_to_mesh
    def test_method(self, ctx, **kwargs):
        return "response from test_method"


async def main():
    service_instance = MeshServiceInstance()

    api = RMQAPI(
        amqp_url=amqp_url,
        service_name=service_instance._service_name,
        instance_id=service_instance._instance_id,
        service_instance=service_instance,
        transport_settings={
            "prefetch_count": 1,
        }
    )
    await api.connect()
    await asyncio.Future()


if __name__ == "__main__":
    log_format = (
        "%(levelname) -10s %(asctime)s %(name) -30s %(funcName) "
        "-35s %(lineno) -5d: %(message)s"
    )
    logging.basicConfig(level=logging.DEBUG, format=log_format)
    logging.getLogger("pika").setLevel(logging.WARNING)
    logging.getLogger("nuropb").setLevel(logging.WARNING)
    logging.getLogger("nuropb_gw").setLevel(logging.INFO)
    asyncio.run(main())
