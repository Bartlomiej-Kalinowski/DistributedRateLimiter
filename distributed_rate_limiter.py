import time
import uuid
from fastapi import HTTPException
from valkey import Valkey
from config import MAX_REQUESTS, TIME_WINDOW
import os


class RateLimiterService:
    def __init__(self):
        host = os.getenv("VALKEY_HOST", "localhost")
        port = int(os.getenv("VALKEY_PORT", 6379))
        self.db = Valkey(host=host, port=port, db=0, decode_responses=True)

    def reset_client(self, client_id: str) -> dict:
        self.db.delete(client_id)
        return {"message": "Zresetowano", "client_id": client_id, "requests_numb": 0}

    def increment_client(self, client_id: str) -> dict:
        now = time.time()
        window_start = now - TIME_WINDOW

        # Czyszczenie przeterminowanych wpisów
        self.db.zremrangebyscore(client_id, 0, window_start)

        # Policz zapytania
        current_requests = self.db.zcard(client_id)

        if current_requests >= MAX_REQUESTS:
            raise HTTPException(
                status_code=429,
                detail="Request limit exceeded (Too Many Requests)"
            )

        # Dodaj zapytanie (z unikalnym ID dla bezpieczeństwa wątkowego)
        req_id = f"{time.time_ns()}:{uuid.uuid4()}"
        self.db.zadd(client_id, {req_id: now})

        # Odśwież TTL
        self.db.expire(client_id, TIME_WINDOW)

        return {
            "message": "Completed",
            "client_id": client_id,
            "requests_numb": current_requests + 1
        }

    def get_client_status(self, client_id: str) -> dict:
        if not self.db.exists(client_id):
            raise HTTPException(status_code=404, detail="Nie znaleziono klienta")

        now = time.time()
        self.db.zremrangebyscore(client_id, 0, now - TIME_WINDOW)

        count = self.db.zcard(client_id)
        ttl = self.db.ttl(client_id)
        return {"client_id": client_id, "requests_numb": count, "ttl_remaining": ttl}

