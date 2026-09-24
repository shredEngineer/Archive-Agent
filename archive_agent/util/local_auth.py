#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

"""
One-password auth for this workstation's local services.

Every service accepts the workstation password (env `LOCAL_AUTH_PASSWORD`) either as
HTTP Basic with any username -- what browsers send -- or as
`Authorization: Bearer <password>` -- what MCP clients and scripts send.
"""

import base64
import binascii
import hmac
import os
import sys
from typing import Any, Optional

ENV_VAR = "LOCAL_AUTH_PASSWORD"


def get_password() -> Optional[str]:
    """
    Get the workstation password.
    :return: Password, or None if unset or empty.
    """
    return os.environ.get(ENV_VAR) or None


def require_password() -> str:
    """
    Get the workstation password, or exit if it is unset (fail closed).
    :return: Password.
    """
    password = get_password()
    if not password:
        sys.exit(f"{ENV_VAR} is not set - refusing to serve without authentication.")
    return password


def password_matches(candidate: str, password: str) -> bool:
    """
    Compare a candidate password in constant time.
    :param candidate: Candidate password.
    :param password: Workstation password.
    :return: True if they match.
    """
    return hmac.compare_digest(candidate.encode(), password.encode())


def authorized(header: Optional[str], password: str) -> bool:
    """
    Check an `Authorization` header (Basic with any username, or Bearer).
    :param header: Header value.
    :param password: Workstation password.
    :return: True if authorized.
    """
    if not header:
        return False
    scheme, _, value = header.partition(" ")
    value = value.strip()
    if scheme.lower() == "bearer":
        candidate = value
    elif scheme.lower() == "basic":
        try:
            candidate = base64.b64decode(value, validate=True).decode("utf-8").partition(":")[2]
        except (binascii.Error, UnicodeDecodeError):
            return False
    else:
        return False
    return password_matches(candidate, password)


class LocalAuthMiddleware:
    """
    Pure ASGI, so it guards websocket upgrades and SSE streams as well as plain HTTP.
    """

    def __init__(self, app: Any, password: str, realm: str):
        """
        Initialize middleware.
        :param app: ASGI app to guard.
        :param password: Workstation password.
        :param realm: Realm shown in the browser login dialog.
        """
        self.app = app
        self.password = password
        self.realm = realm

    async def __call__(self, scope, receive, send):
        if scope["type"] not in ("http", "websocket"):
            return await self.app(scope, receive, send)
        header = dict(scope["headers"]).get(b"authorization", b"").decode("latin-1")
        if authorized(header, self.password):
            return await self.app(scope, receive, send)
        if scope["type"] == "websocket":
            await send({"type": "websocket.close", "code": 1008})
            return
        await send({
            "type": "http.response.start",
            "status": 401,
            "headers": [
                (b"www-authenticate", f'Basic realm="{self.realm}"'.encode()),
                (b"content-type", b"text/plain; charset=utf-8"),
            ],
        })
        await send({"type": "http.response.body", "body": b"Unauthorized"})
