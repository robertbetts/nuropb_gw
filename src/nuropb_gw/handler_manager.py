import logging
from typing import Any, Dict, Set, List, Optional, Callable
import json

logger = logging.getLogger(__name__)


class HandlerManager:
    """HandlerManager is responsible for the management of consumer connection handlers,
    and does the following:
    * Registers handlers for incoming connections
    * Unregistering handlers for closed connections
    * Authorization validation of new connections
    * Receiving messages from handlers
    * Sending messages to handlers
    * Sending messages to:
      * all registered handlers
      * one specific handler
      * all handlers registered to one user or a set of specific users

    Handlers can be any WebSocket or TCP connection, however the design is targeted
    for WebSocket connections.

    NOTE: An authorized user might have many concurrent connections, this is the
    reason for a user_id to session_id mapping, this allows directed user
    communications to span all their connections.
    """
    _service_name: str
    _instance_id: str
    _session_id_to_handler: Dict[str, "Handler"]
    _user_id_to_session_ids: Dict[str, Set[str]]
    _on_handler_message_received: Callable[[..., Any], Any] | None
    """A callback set by the ServiceMeshManager to receive incoming messages from handlers.
    these incoming messages are asynchronously processed by the ServiceMeshManager. 
    Incoming messages are not queued or explicitly persisted before processing and 
    forwarding on to the service mesh.
    """

    _max_concurrent_connections: int

    def __init__(
            self,
            service_name: str,
            instance_id: str,
            on_handler_message_received: Optional[Callable[[..., Any], Any]] = None
    ):
        self._service_name = service_name
        self._instance_id = instance_id
        self._session_id_to_handler = {}
        self._user_id_to_session_ids = {}
        self._on_handler_message_received = on_handler_message_received

        self._max_concurrent_connections = 0

    async def on_handler_message(self, handler, message: str) -> None:
        """ Called from a handler, when new message received over the handler's connection.

        *NOTE* a response from a self._on_handler_message_received call (below) is awaited.
        Messages received from the handler are not queued, and are processed in order. However,
        due to the asynchronous nature of the service mesh, responses back to the handler can
        be received out of the order in which they were sent.

        If the response time for the below call is (N) seconds, if a second message is
        received from the handler immediately after this message. The second message
        could be processed before the response to the first message is received.

        If the response time for the second message is < (N) seconds, then the response
        will be transmitted back to the handler before the response to the first message is
        received.

        JSON decoding / encoding: decoding is handled here, encoding is handled directly
        by the handler.

        :param handler: Handler instance
        :param message: JSON encoded string
        :return:
        """
        if self._on_handler_message_received:
            try:
                msg_dict = json.loads(message)
                await self._on_handler_message_received(self.to_handler_message, handler, msg_dict)
            except Exception as e:
                logger.error("Error decoding JSON, error: %s",  e)
                logger.debug("Error decoding JSON, message: %s",  message)
                message = {
                    "error": type(e).__name__,
                    "description": f"Error decoding JSON: {e}",
                }
                await self.to_handler_message(handler, message)
        else:  # pragma: no cover
            raise RuntimeError("on_handler_message_received callback has not been configured")

    async def to_handler_message(self, handler, message) -> None:
        """ Sends a service mesh message to the handler. This method is passed as a
        callback to the service mesh manager.

        JSON encoding is handled directly by the handler,
        JSON decoding is handled in by self.on_handler_message

        :param handler:
        :param message:
        :return:
        """
        _ = self
        logger.debug("Service mesh response for session_id: %s, user_id: %s",
                     *[handler.session_id, handler.user_id])
        logger.debug("Message: %s", message)
        await handler.write_message(message)

    def get_handler(self, session_id: str) -> Optional["Handler"]:
        """Returns a handler from session id, None if not found
        """
        return self._session_id_to_handler.get(session_id, None)

    def register(self, handler: "Handler") -> None:
        """Registers a handler
        """
        self._session_id_to_handler[handler.session_id] = handler
        sessions = self._user_id_to_session_ids.setdefault(handler.user_id, set())
        sessions.add(handler.session_id)
        self._user_id_to_session_ids[handler.user_id] = sessions
        logger.debug(f"Registered WebSocket handler: session_id: {handler.session_id}, user_id: {handler.user_id}")
        connections = len(self._session_id_to_handler)
        if connections > self._max_concurrent_connections:
            self._max_concurrent_connections = connections
            logger.critical(f"Highest concurrent connections: reached {self._max_concurrent_connections}")

    def unregister(self, handler: "Handler") -> None:
        """Unregisters a handler
        """
        if handler.session_id in self._session_id_to_handler:
            del self._session_id_to_handler[handler.session_id]
        user_info = handler.get_current_user()
        if user_info and user_info["user_id"] in self._user_id_to_session_ids:
            sessions = self._user_id_to_session_ids[user_info["user_id"]]
            sessions.discard(handler.session_id)
            if len(sessions) == 0:
                del self._user_id_to_session_ids[user_info["user_id"]]
            else:
                self._user_id_to_session_ids[user_info["user_id"]] = sessions

    async def send_message(self, session_id: str, message: str) -> None:
        """Sends the message to the handler
        """
        if session_id in self._session_id_to_handler:
            await self._session_id_to_handler[session_id].write_message(message)

    async def send_message_to_user_ids(self, user_ids: List[str], message: str) -> None:
        """Sends the message to all handlers for all given user_ids
        There is no intention to support an additional method for a single user,
        for that use case provide a list with one user_id.
        """
        handlers: Set["Handler"] = set()

        def flatten(session_ids) -> None:
            [
                handlers.add(self._session_id_to_handler.get(session_id))
                for session_id in session_ids
                if session_id in self._session_id_to_handler
            ]

        user_sessions = [
            self._user_id_to_session_ids.get(user_id, set()) for user_id in user_ids
        ]
        _ = [flatten(item) for item in user_sessions]
        _ = [await handler.write_message(message) for handler in handlers]
        logger.debug("Sending message completed to user ids: %s", user_ids)

    async def send_message_to_all(self, message: str):
        """Sends the message to all handlers
        """
        _ = [
            await handler.write_message(message)
            for handler in self._session_id_to_handler.values()
        ]
        logger.debug("Sending message completed to all")

    def close(self, session_id: str):
        """Close a handler
        """
        if session_id in self._session_id_to_handler:
            try:
                self._session_id_to_handler[session_id].close()
            except Exception as e:  # pragma: no cover
                # too much noise to log this in production
                _ = e
                logger.error(f"Error closing handler: {session_id}: {e}")

        logger.debug(f"Closed handler for session_id: {session_id}")

    def close_user_ids(self, user_ids: List[str]):
        """Close a handlers for all user_ids provided
        """
        handlers: Set["Handler"] = set()

        def flatten(session_ids) -> None:
            [
                handlers.add(self._session_id_to_handler.get(session_id))
                for session_id in session_ids
                if session_id in self._session_id_to_handler
            ]

        user_sessions = [
            self._user_id_to_session_ids.get(user_id, set()) for user_id in user_ids
        ]
        _ = [flatten(item) for item in user_sessions]
        _ = [handler.close() for handler in handlers]
        logger.debug("Closed handlers for all user_ids: %s", user_ids)

    def close_all(self):
        """Close all handlers
        """
        _ = [handler.close() for handler in self._session_id_to_handler.values()]
        logger.debug("Close all handlers completed")
