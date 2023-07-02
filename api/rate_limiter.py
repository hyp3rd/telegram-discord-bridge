"""Rate Limiter for the Bridge API"""
from collections import defaultdict
from time import time

from fastapi import Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.status import HTTP_429_TOO_MANY_REQUESTS


# Rate Limiting Middleware
class RateLimitMiddleware(BaseHTTPMiddleware):  # pylint: disable=too-few-public-methods
    """Rate Limiting Middleware for the Bridge API"""

    def __init__(self, app, limit=100, interval=60):
        super().__init__(app)
        self.limit = limit
        self.interval = interval
        self.requests = defaultdict(list)

    async def dispatch(self, request, call_next):
        if request.client is not None:
            client_ip = request.client.host
        else:
            client_ip = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        request_times = self.requests[client_ip]
        request_times = [t for t in request_times if time() - t < self.interval]
        self.requests[client_ip] = request_times

        if len(request_times) >= self.limit:
            return RateLimitResponse()

        self.requests[client_ip].append(time())
        return await call_next(request)


class RateLimitResponse(Response):
    """Rate Limit Response for the Bridge API"""

    media_type = "application/json"

    def __init__(self):
        super().__init__(
            status_code=HTTP_429_TOO_MANY_REQUESTS,
            content='{"detail": "Too many requests"}',
        )
