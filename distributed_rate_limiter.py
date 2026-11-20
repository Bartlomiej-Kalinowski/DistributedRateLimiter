import os
import time
import uuid

from fastapi import HTTPException
from valkey import Valkey

from config import MAX_REQUESTS, TIME_WINDOW


class RateLimiterService:
    def __init__(self):
        host = os.getenv("VALKEY_HOST", "localhost")
        port = int(os.getenv("VALKEY_PORT", 6379))  # fixed port, to be changed in the future
        self.db = Valkey(host=host, port=port, db=0, decode_responses=True)
        self._increment_script = self.db.register_script(
            """
            local key = KEYS[1]
            local now = tonumber(ARGV[1])
            local window_seconds = tonumber(ARGV[2])
            local max_requests = tonumber(ARGV[3])
            local request_id = ARGV[4]

            local window_start = now - window_seconds
            redis.call("ZREMRANGEBYSCORE", key, 0, window_start)

            local current_requests = redis.call("ZCARD", key)
            if current_requests >= max_requests then
                return {0, current_requests}
            end

            redis.call("ZADD", key, now, request_id)
            redis.call("EXPIRE", key, math.ceil(window_seconds))

            return {1, current_requests + 1}
            """
        )
        self._status_script = self.db.register_script(
            """
            local key = KEYS[1]
            local now = tonumber(ARGV[1])
            local window_seconds = tonumber(ARGV[2])

            if redis.call("EXISTS", key) == 0 then
                return {-1, -1}
            end

            redis.call("ZREMRANGEBYSCORE", key, 0, now - window_seconds)
            local count = redis.call("ZCARD", key)
            local ttl = redis.call("TTL", key)
            return {count, ttl}
            """
        )
        self._fixed_window_script = self.db.register_script(
            """
            local key = KEYS[1]
            local window_seconds = tonumber(ARGV[1])
            local max_requests = tonumber(ARGV[2])
            local current_requests = tonumber(redis.call("GET", key) or "0")

            if current_requests >= max_requests then
                return {0, current_requests, redis.call("TTL", key)}
            end

            current_requests = redis.call("INCR", key)
            if current_requests == 1 then
                redis.call("EXPIRE", key, window_seconds)
            end

            return {1, current_requests, redis.call("TTL", key)}
            """
        )

    def reset_client(self, client_id: str) -> dict:
        self.db.delete(client_id, f"fixed-window:{client_id}")
        return {"message": "Zresetowano", "client_id": client_id, "requests_numb": 0}

    def increment_client(self, client_id: str) -> dict:
        now = time.time()
        req_id = f"{time.time_ns()}:{uuid.uuid4()}"
        allowed, requests_count = self._increment_script(
            keys=[client_id],
            args=[now, TIME_WINDOW, MAX_REQUESTS, req_id],
        )

        if int(allowed) == 0:
            raise HTTPException(
                status_code=429,
                detail="Request limit exceeded (Too Many Requests)",
            )

        return {
            "message": "Completed",
            "client_id": client_id,
            "requests_numb": int(requests_count),
        }

    def increment_fixed_window_client(self, client_id: str) -> dict:
        allowed, requests_count, ttl = self._fixed_window_script(
            keys=[f"fixed-window:{client_id}"],
            args=[TIME_WINDOW, MAX_REQUESTS],
        )

        if int(allowed) == 0:
            raise HTTPException(
                status_code=429,
                detail="Request limit exceeded (Too Many Requests)",
            )

        return {
            "message": "Completed",
            "client_id": client_id,
            "requests_numb": int(requests_count),
            "ttl_remaining": int(ttl),
        }

    def get_client_status(self, client_id: str) -> dict:
        now = time.time()
        count, ttl = self._status_script(
            keys=[client_id],
            args=[now, TIME_WINDOW],
        )

        if int(count) == -1:
            raise HTTPException(status_code=404, detail="Nie znaleziono klienta")

        return {
            "client_id": client_id,
            "requests_numb": int(count),
            "ttl_remaining": int(ttl),
        }
