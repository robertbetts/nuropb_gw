import json
import logging
import asyncio
import random
import time
from multiprocessing import Pool
import datetime

from nuropb_gw.testing.stubs import TEST_AUTH_TOKENS, websocket_client

logger = logging.getLogger(__name__)


class WSClient:
    _url: str
    _authorization: str
    _running: bool
    _batch_size: int
    _send_interval: float

    def __init__(self, url: str, batch_size: int = 10000, send_interval: float = 0):
        self._authorization = random.choice(TEST_AUTH_TOKENS)
        self._running = False
        self._test_count = 0
        self._url = url
        self._batch_size = batch_size
        self._send_interval = send_interval

    def stop(self):
        self._running = False

    async def __call__(self):
        headers = {
            "Authorization": f"Bearer {self._authorization}",
        }
        ws_conn = await websocket_client(self._url, headers=headers)
        self._running = True
        start_time = time.time()

        while self._running:
            try:
                hello_message = await ws_conn.read_message()
                logger.debug("hello_message: %s", hello_message)

                async def send_message(conn) -> None:
                    await asyncio.sleep(self._send_interval)
                    message = {
                        "type": "request",
                        "payload": {
                            "service": "mesh-test",
                            "method": "test_method",
                            "params": {
                                "param1": "value1",
                            },
                            "trace_id": "test_trace_id",
                        },
                    }
                    json_message = json.dumps(message)
                    await conn.write_message(json_message)
                    response = await conn.read_message()
                    self._test_count += 1
                    # logger.debug("Response message: %s", response)
                    return None

                _ = [await send_message(ws_conn) for _ in range(self._batch_size)]

            except Exception as err:
                logger.error(err)
                self._running = False
            finally:
                self.stop()
        end_time = time.time()

        logger.info(f"test_count: {self._test_count}")
        logger.info(f"total_seconds: {end_time - start_time}")
        logger.info(f"average_requests_per_second: {self._test_count / (end_time - start_time)}")
        logger.info(f"average_seconds_per_request: {(end_time - start_time) / self._test_count}")

        return {
            "taken": end_time - start_time,
            "count": self._test_count,
        }


def spawn(params):
    url, batch_size, send_interval = params
    test_client = WSClient(url, batch_size, send_interval)
    return asyncio.run(test_client())


async def main():
    ws_url = "ws://localhost:9080/websocket"
    single_run = False
    if single_run:
        test_client = WSClient(ws_url, batch_size=1)
        await test_client()
    else:
        batch_size = 10000
        pool_size = 5
        start_time = time.time()
        with Pool(pool_size) as p:
            results = p.map(spawn, [(ws_url, batch_size, 0) for _ in range(pool_size)])
            logger.info(results)
        end_time = time.time()

        swarm_test_count = sum([result["count"] for result in results])
        swarm_total_time = sum([result["taken"] for result in results])

        logger.info("batch size: %s", batch_size)
        logger.info("swarm size: %s", pool_size)
        logger.info(f"total swarm completed test_count: {swarm_test_count}")

        logger.info(f"swarm_total_time: {swarm_total_time}")
        logger.info(f"swarm average time per batch: {swarm_total_time / pool_size}")
        logger.info(f"swarm_average_requests_per_second: {swarm_test_count / swarm_total_time}")
        logger.info(f"swarm_average_seconds_per_request: {swarm_total_time / swarm_test_count}")

        logger.info(f"test_total_seconds: {end_time - start_time}")
        td = datetime.timedelta(seconds=swarm_total_time)
        logger.info(f"time if tests ran sequentially: {td}")
        logger.info(f"test_average_requests_per_second: {swarm_test_count / (end_time - start_time)}")
        logger.info(f"test_average_seconds_per_request: {(end_time - start_time) / swarm_test_count}")


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
