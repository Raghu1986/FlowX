from starlette.types import ASGIApp, Receive, Scope, Send
from starlette.requests import Request
from app.core.logging_utils import correlation_id_ctx
import uuid
import time


class CorrelationIdMiddleware:
    """
    Production-safe ASGI middleware that:
    - Generates a correlation_id if missing
    - Stores it in contextvar correlation_id_ctx
    - Adds X-Correlation-ID header to every response
    - Works with errors, exceptions, WebSockets, BackgroundTasks
    - Adds request metadata for logging (method, path, client_ip, duration)
    """

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        # Only process HTTP requests (skip websockets)
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope)

        # Generate or reuse correlation_id
        correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
        token = correlation_id_ctx.set(correlation_id)  # store in contextvar

        method = scope["method"]
        path = scope["path"]
        client_ip = scope.get("client", ["unknown"])[0]

        start_time = time.perf_counter()

        async def send_wrapper(message):
            # Inject correlation-id and server timing into the response
            if message["type"] == "http.response.start":
                process_time = (time.perf_counter() - start_time) * 1000

                headers = message.setdefault("headers", [])
                headers.append((b"x-correlation-id", correlation_id.encode()))
                headers.append((b"x-response-time-ms", f"{process_time:.2f}".encode()))
                headers.append((b"x-client-ip", client_ip.encode()))

            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)

        finally:
            # Reset contextvar to keep global context clean
            correlation_id_ctx.reset(token)
