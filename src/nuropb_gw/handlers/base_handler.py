import logging
from typing import Callable, Optional, Dict, Any
import datetime

from tornado.web import RequestHandler
import tornado.escape

logger = logging.getLogger(__name__)


_CHECK_PREFIX_CONFIG = ("Bearer :", "Bearer:", "Bearer ", "Bearer")


def strip_bearer_token(bearer_token: str | None) -> str | None:
    """Strip the Bearer token prefix from the bearer token string

    :param bearer_token:
    :return: Bearer token string without the Bearer prefix
    """
    if not bearer_token:
        return bearer_token
    for prefix in _CHECK_PREFIX_CONFIG:
        if bearer_token.startswith(prefix):
            bearer_token = bearer_token[len(prefix):].strip()
            break
    return bearer_token


class AuthenticateMixin(RequestHandler):
    """Mixin for authenticating handler instances
    """

    _user_cache: Optional[Dict[str, Any]]
    """_user_cache is for convenience, avoiding potentially expensive calls validating 
    Authorization tokens and or retrieving cached session information.
    """
    _allow_authorisation_cookie: bool
    _authentication_timeout: int | None
    """_authentication_timeout is the number of minutes before authentication expires, and
    is used to set the session cookie expiry time. If None, the session cookie will not expire.
    """
    _authorise_header_name: str
    _authorise_cookie_name: str
    _authorise_from_token: Callable[[str], Optional[Dict[str, Any]]] | None

    def initialize(self, **kwargs) -> None:
        self.require_setting("session_cookie_name", "user session tracking cookie name")
        self.require_setting("cookie_secret", "secret for encoding secure cookies")
        self.require_setting(
            "authentication_timeout", "number of minutes before authentication expires"
        )
        self._allow_authorisation_cookie: bool = self.settings[
            "allow_authorisation_cookie"
        ]
        time_out = self.settings["authentication_timeout"]
        self._authentication_timeout = None if (isinstance(time_out, int) and time_out < 1) else time_out
        self._authorise_header_name = self.settings.get("authorise_header_name", "Authorization")
        self._authorise_cookie_name = self.settings.get("authorise_cookie_name", "Authorization")
        self._authorise_from_token = self.settings.get("authorise_from_token", None)
        self._user_cache = None

    """ NOTE: here as reference only
    # def set_default_headers(self):
    #     self.set_header("Access-Control-Allow-Origin", "*")
    #     self.set_header("Access-Control-Allow-Headers", "x-requested-with")
    #     self.set_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')
    #     self.set_header("Content-Type", "application/json")
    """

    def get_user_information_from_bearer_token(
        self, bearer_token: str
    ) -> Optional[Dict[str, Any]]:
        """ Gets user information from a bearer token, update this method as per your
        authentication pattern.

        If a token is revoked or has expired, it is expected that self._authorise_from_token(bearer_token)
        would return None.

        :param bearer_token:
        :return: User information dictionary or None
        """
        bearer_token = strip_bearer_token(bearer_token)
        if not bearer_token:
            return None
        if callable(self._authorise_from_token):
            user_info = self._authorise_from_token(bearer_token)
            return user_info
        else:  # pragma: no cover
            logging.debug("Bearer token present, however authorise_from_token() was not configured.")
            return None

    def has_authorisation_expired(self) -> bool:
        """ This function declaration is here for reference only and represents an abstraction for
        determining if a users authorisation has expired, and available for customization
        dependent on derivative implementations specific needs.

        Default session identification supports the following:
        * tokens: These will contain an expiry claim and will be validated in the
            get_user_information_from_bearer_token() method
        * session_cookie: when a session cookie expires, the user will be required to
            re-authenticate.

        Hence, the "out of the" box user authorisation methods cover this requirement as is.

        *WEBSOCKETS* - Websockets are a special case, as they do not support cookies and are
        long-lived session that could be open for days. In this case, there is a requirement
        to periodically check if the user's authorisation has expired. This is left to the
        websocket handler implementation.
        *NOTE* It's also likely that the user identification methods for websockets will be
        identical to other handlers, unless authentication is handled over the websocket
        protocol. Therefore, beyond instantiating the handler and opening the websocket
        connection, the has_authorisation_expired() would be checked during incoming and
        outgoing messages events.
        """
        _ = self  # pylint: disable=unused-variable
        return False

    def _process_user_info(self, user_info, message):
        """ utility method to reduce complexity from self.get_current_user()
        :param user_info:
        :param message:
        :return:
        """
        if user_info and not self.has_authorisation_expired():
            user_info["last_activity"] = f"{datetime.datetime.now(datetime.timezone.utc).isoformat()}Z"
            self.update_user_info(user_info=user_info)
        return user_info

    def get_current_user(self) -> Optional[Dict[str, Any]]:
        """Returns the minimum user information from the session cookie or Authorisation cookie (bearer token)
        in order to identify the user and their session.

        An Authentication from cookies is only valid for GET and HEAD methods.
        An Authentication from headers is valid for all methods.

        Order of preference is:
        1. Authorisation header
        2. Authorisation cookie
        3. Session cookie

        user information details:
         - session_id: str - a unique webserver session or websocket connection identifier
         - user_id: str - system unique user identifier, often the same the username
         - username : str - username required when providing user credentials
         - last_activity: str - UTC iso formatted time
         - bearer_token: str - jwt

        :return: User information dictionary or None
        """

        """_user_cache is for convenience, avoiding potentially expensive calls validating 
        Authorization tokens and or retrieving cached session information.
        """

        user_info = self._user_cache

        if user_info is None:
            # First check for header Authorization token
            bearer_token = self.request.headers.get(self._authorise_header_name, None)
            user_info = self._process_user_info(
                user_info=self.get_user_information_from_bearer_token(bearer_token),
                message=f"Authenticated from Authentication header: {bearer_token}"
            )

        if user_info is None and self.request.method in ("GET", "HEAD"):
            # First check for cookie Authorization token
            if self._authorise_cookie_name:
                bearer_token = self.get_cookie(self._authorise_cookie_name, default=None)
                user_info = self._process_user_info(
                    user_info=self.get_user_information_from_bearer_token(bearer_token),
                    message=f"Authenticated from Authentication cookie: {bearer_token}"
                )

            if user_info is None:
                # Finally check for session cookie
                session_cookie_name = self.settings["session_cookie_name"]
                user_cookie = self.get_signed_cookie(session_cookie_name)
                try:
                    user_info = self._process_user_info(
                        user_info=tornado.escape.json_decode(user_cookie),
                        message=f"Authenticated from session cookie: {session_cookie_name}"
                    )
                except Exception as err:  # pylint: disable=broad-except
                    _ = err
                    user_info = None

        return user_info




class BaseMixin(AuthenticateMixin):
    """Base class for all handlers and extends the AuthenticateMixin
    providing authentication and authorisation methods.
    """

    def initialize(self, **kwargs):
        """ Initialize the handler and inherit the AuthenticateMixin initialize settings
        """
        AuthenticateMixin.initialize(self, **kwargs)
