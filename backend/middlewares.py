# backend/middlewares.py
from uuid import uuid4
import logging
from typing import Callable, Awaitable, Dict, Any

from backend.logging_config import set_job_id, clear_job_id, set_user, clear_user

logger = logging.getLogger("irricontrol")


class RequestContextMiddleware:
    """
    Middleware ASGI:
    - Extrai/gera X-Request-ID por request.
    - Injeta em contextvars (job_id) para logs correlacionados.
    - Adiciona X-Request-ID na resposta.
    - (Opcional) seta 'user' se algum middleware anterior popular scope['state'].user.
    """

    def __init__(self, app: Callable[..., Awaitable[None]]):
        self.app = app

    async def __call__(self, scope: Dict[str, Any], receive, send):
        if scope.get("type") != "http":
            # Não é HTTP (ex.: websocket) -> segue reto
            await self.app(scope, receive, send)
            return

        # Extrai headers da conexão
        headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope.get("headers", [])}
        req_id = headers.get("x-request-id") or str(uuid4())
        set_job_id(req_id)

        # Extrai user se existir (depende de autenticação própria do app)
        user_identifier = None
        state = scope.get("state")
        if state is not None and hasattr(state, "user") and getattr(state, "user"):
            user_identifier = str(getattr(state, "user"))
            set_user(user_identifier)

        method = scope.get("method", "-")
        path = scope.get("path", "-")
        status_code = None

        logger.info("➡️ %s %s", method, path)

        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message.get("status", None)
                # Garante X-Request-ID na resposta
                hdrs = list(message.get("headers") or [])
                hdrs.append((b"x-request-id", req_id.encode("latin-1")))
                message["headers"] = hdrs
            return await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
            logger.info("✅ %s %s -> %s", method, path, status_code if status_code is not None else "-")
        except Exception as exc:
            logger.exception("❌ Unhandled exception: %s", exc)
            raise
        finally:
            clear_user()
            clear_job_id()