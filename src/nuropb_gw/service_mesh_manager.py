import logging
from typing import Any, Dict, List, Optional, Tuple, Type
import asyncio
from uuid import uuid4

from nuropb.rmq_api import RMQAPI

from nuropb_gw.handler_manager import HandlerManager


logger = logging.getLogger(__name__)

HandlerType = Type["Handler"]

RequestFutureResponse = Tuple[asyncio.Future[Any], str, str, str]
""" RequestFutureResponse:
- Awaitable
- trace_id
- session_id
- user_id
"""


class ServiceMeshManagerController:
    """A ServiceMeshManagerController provides the ServiceMeshManager with curated
    visibility to the service mesh. Only the exposed methods of the
    ServiceMeshManagerController are available to other service mesh services.

    The ServiceMeshManagerController is not intended to interact with any handlers
    directly.

    This is an implementation stub, and is intended to be extended by with
    implementation specific requirements
    """

    _service_name: str
    _instance_id: str
    _event_topic_subscriptions: List[str]

    def __init__(
        self,
        service_name: str,
        instance_id: str,
        event_topic_subscriptions: Optional[List[str]] = None,
    ):
        self._service_name = service_name
        self._instance_id = instance_id
        self._event_topic_subscriptions = event_topic_subscriptions or []

    @property
    def service_name(self) -> str:
        return self._service_name

    @property
    def instance_id(self) -> str:
        return self._instance_id

    @property
    def event_topic_subscriptions(self) -> List[str]:
        return self._event_topic_subscriptions

    def _handle_event_(
        self, topic: str, event: Any, context: Optional[Dict[str, Any]]
    ) -> None:
        """This method is called from Service Mesh API when an event is received
        :param topic:
        :param event:
        :param context:
        :return: Nothing
        """


class ServiceMeshManager:
    """The ServiceMeshManager, is responsible for proxying communications to the
    service mesh and does the following:
    * Manages a (NuroPb API) connection to the service mesh.
    * Passes messages between HandlerManager and the service mesh API
    * Tracks the state of asynchronous requests from handlers and directs responses
      from the service mesh back to the originating handler.
    * Is responsible for its and only its, connection authorisation to the service mesh
      transport layer and broker. NOT any on-behalf-of authorisation for handler
      connections.
    """

    _service_controller: ServiceMeshManagerController
    _sm_api: RMQAPI
    _handler_manager: HandlerManager

    def __init__(
        self,
        service_name: str,
        instance_id: str,
        amqp_url: str,
        handler_manager: HandlerManager,
        service_controller: ServiceMeshManagerController | None = None,
    ):
        self._running_future = None
        self._service_controller = service_controller or ServiceMeshManagerController(
            service_name=service_name,
            instance_id=instance_id,
        )
        self._sm_api = RMQAPI(
            service_name=service_name,
            instance_id=instance_id,
            service_instance=self._service_controller,
            amqp_url=amqp_url,
            transport_settings={
                "event_bindings": self._service_controller.event_topic_subscriptions,
                "prefetch_count": 1,
                "default_ttl": 60 * 60 * 1000,  # 1 hour
            },
        )
        self._handler_manager = handler_manager
        self._handler_manager._on_handler_message_received = (
            self._on_handler_message_received
        )

    @property
    def connected(self) -> bool:
        return self._sm_api.connected

    def connect(self) -> None:
        def done(_future):
            logger.debug("Service Mesh Manager connected")

        task = asyncio.create_task(self._sm_api.connect())
        task.add_done_callback(done)

    def disconnect(self) -> None:
        asyncio.create_task(self._sm_api.disconnect())

    async def handle_request(
        self, handler_response_cb, handler, payload: Dict[str, any]
    ) -> None:
        """This method is called from HandlerManager when a message is received from a handler.
        :param handler_response_cb:
        :param handler:
        :param payload:
        :return: Nothing
        """
        trace_id = payload.get("trace_id", uuid4().hex)
        context = {
            "user_id": handler.user_id,
            "Authorisation": handler.bearer_token,
            "trace_id": trace_id,
        }
        service = payload["service"]
        method = payload["method"]
        params = payload["params"]
        result = await self._sm_api.request(
            service=service,
            method=method,
            params=params,
            context=context,
            trace_id=trace_id,
            rpc_response=False,
        )
        logger.debug("Response from service mesh received: %s", result)
        if result["tag"] in "response":
            response = {
                "type": "response",
                "payload": {
                    "trace_id": trace_id,
                    "result": result["result"],
                    "error": result["error"],
                },
            }
            await handler_response_cb(handler, response)

        elif result["tag"] in "request":
            response = {
                "type": "response",
                "payload": {
                    "trace_id": trace_id,
                    "result": None,
                    "error": result["error"],
                },
            }
            await handler_response_cb(handler, response)

        else:
            logger.error(
                "Service Mesh Manager received unexpected response: %s", result
            )

    async def _on_handler_message_received(
        self, handler_response_cb, handler, message: Any
    ):
        """This method is injected into the Handler Service Manager and called from
        the HandlerManager when a message is received from a handler.

        The handler_response_cb is executed in the HandlerManager and has (handler, message)
        as arguments.

        :param handler_response_cb:
        :param handler:
        :param message:
        :return:
        """
        logger.debug(
            "Received a message from handler session_id %s, user_id: %s",
            *[handler.session_id, handler.user_id]
        )
        mesg_type = message.get("type", None)
        if mesg_type is None:
            logger.error("Message type is not defined")
            return
        payload = message.get("payload", None)
        if payload is None:
            logger.error("Message payload is not defined")
            return
        if mesg_type == "request":
            await self.handle_request(
                handler_response_cb=handler_response_cb,
                handler=handler,
                payload=payload,
            )
        else:
            logger.error(
                "Service Mesh Manager received unexpected response: %s", payload
            )
