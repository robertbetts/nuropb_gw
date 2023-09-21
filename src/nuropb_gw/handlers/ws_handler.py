import logging
from abc import ABC
from typing import Sequence, Any
from uuid import uuid4
import urllib.parse

from tornado.websocket import WebSocketHandler

from nuropb.encodings.serializor import encode_payload
from nuropb_gw.handlers.base_handler import BaseMixin
from nuropb_gw.handler_manager import HandlerManager

logger = logging.getLogger(__name__)


VALID_SESSION_REQUIRED = "A valid user authorisation is required before a WebSocket connection is established"


class WsHandler(WebSocketHandler, BaseMixin, ABC):
    """A Tornado WebSocket handler that does the following:
    * Authorizing and establishing a WebSocket connection
    * Receiving messages over the connection
    * Sending messages over the connection
    * Registering with the handler manager
    * Unregistering with the handler manager

    NOTE: A WebSocket connection can be seamlessly established after a valid web session
     using the SameSite session cookie. In addition, bearer token authentication is also
     supported. Where a bearer token present is either present in the Authentication
     header, or Authorisation cookie, and in that order of preference. this token would
     override the session cookie.

    The bearer token pattern is easily extended to support other authentication methods
        such as API Keys, OpenID, OAuth2, or SAML.
    """

    _allowed_origins: Sequence[str]
    _handler_manager: HandlerManager
    _session_id: str
    _user_id: str | None
    _username: str | None
    _bearer_token: str | None

    def initialize(self):
        BaseMixin.initialize(self)
        self.require_setting(
            "allowed_origins",
            "list of domains allowed to connect, eg: ['.my-domain.com']",
        )
        self.require_setting("handler_manager", "HandlerManager instance")
        self._allowed_origins = self.settings["allowed_origins"]
        self._handler_manager = self.settings["handler_manager"]
        self._session_id = uuid4().hex
        self._user_id = None
        self._username = None
        self._bearer_token = None

    @property
    def session_id(self) -> str:
        """Returns the session id for the WebSocket handler"""
        return self._session_id

    @property
    def user_id(self) -> str:
        """Returns the user id for the WebSocket handler"""
        return self._user_id

    @property
    def username(self) -> str:
        """Returns the username for the WebSocket handler"""
        return self._username

    @property
    def bearer_token(self) -> str:
        """Returns a bearer token for the WebSocket handler"""
        return self._username

    def check_origin(self, origin: str) -> bool:
        if not self._allowed_origins:
            logger.debug(f"Rejected origin: {origin}, no allowed origins configured")
            return False

        if self._allowed_origins and "*" in self._allowed_origins:
            logger.debug(f"Accepted origin {origin} for rule *")
            return True

        parsed_origin = urllib.parse.urlparse(origin)
        if parsed_origin.netloc:
            for origin in self._allowed_origins:
                if parsed_origin.netloc.endswith(origin):
                    logger.debug(f"Accepted origin {origin}")
                    return True
        logger.debug(f"Rejected origin {origin}")
        return False

    async def open(self):
        """Called on a WebSocket connection opened event

        If the Authorization for the connection can not be established, then it is closed
        """
        user_info = self.get_current_user()
        if user_info is None:
            self.close()
            return
        self._user_id = user_info["user_id"]
        self._username = user_info["username"]
        self._bearer_token = user_info["bearer_token"]

        """ After successful authorization, register the handler with the handler manager
        """
        self._handler_manager.register(self)

        """ On completed registration reply with a hello message to inform the connection 
        consumer of the session_id and user_id assigned to the connection
        """
        logger.debug(
            "WebSocket opened, user_id: %s, session_id: %s",
            *[self._user_id, self._session_id],
        )
        hello_message = {
            "type": "event",
            "payload": {
                "topic": "hello",
                "event": {
                    "session_id": self._session_id,
                    "user_id": self._user_id,
                    "username": self._username,
                },
            },
        }
        await self.write_message(hello_message)

    async def on_message(self, message: str):
        """Message received over WebSocket as an expected json string, pass it directly
        to the service manager for further processing"""
        logger.debug("WebSocket message received: %s", message)
        await self._handler_manager.on_handler_message(self, message)

    async def write_message(self, message: Any, binary: bool = False) -> None:
        """Writes a message to the WebSocket, if not binary then serialize the message
        to json first. It is safe to call this method regardless of the state of the
        WebSocket connection.

        JSON encoding done here, and handling all data type that are not json serializable.

        *NOTE* JSON decoding is handled in the handler manager.
        """
        logger.debug(f"WebSocket message sending: {message}")
        try:
            if not binary:
                message = encode_payload(message)
            await super().write_message(message=message, binary=binary)
        except Exception as e:
            logger.debug(
                "Error writing to WebSocket session_id: %s, user_id: %s : %s",
                *[self._session_id, self._user_id, e],
            )

    def on_close(self):
        logging.info(
            f"WebSocket closed, session_id: {self._session_id}, user_id: {self._user_id}"
        )
        self._handler_manager.unregister(self)

    def safe_close(self):
        """Idempotent close method, closes the WebSocket connection regardless of state"""
        try:
            self.close()
        except Exception as e:
            logger.debug(
                "Error closing WebSocket session_id: %s, user_id: %s : %s",
                *[self._session_id, self._user_id, e],
            )
