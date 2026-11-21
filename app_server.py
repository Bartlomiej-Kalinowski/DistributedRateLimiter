from __future__ import annotations

import threading
import time
import uvicorn
from fastapi import Depends, FastAPI, Header, Request

from distributed_rate_limiter import RateLimiterService


def resolve_client_id(
    request: Request,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> str:
    if x_api_key and x_api_key.strip():
        return f"apikey:{x_api_key.strip()}"

    client_ip = request.client.host if request.client is not None else "unknown"
    return f"ip:{client_ip}"


def create_app() -> FastAPI:
    app = FastAPI(title="Valkey Rate Limiter API")
    limiter_service = RateLimiterService()

    def get_limiter() -> RateLimiterService:
        return limiter_service

    @app.post("/increment")
    async def increment_identified_client(
        client_id: str = Depends(resolve_client_id),
        service: RateLimiterService = Depends(get_limiter),
    ):
        return service.increment_client(client_id)

    @app.post("/increment/fixed-window")
    async def increment_identified_fixed_window_client(
        client_id: str = Depends(resolve_client_id),
        service: RateLimiterService = Depends(get_limiter),
    ):
        return service.increment_fixed_window_client(client_id)

    @app.post("/increment/naive")
    async def increment_identified_naive_client(
        client_id: str = Depends(resolve_client_id),
        service: RateLimiterService = Depends(get_limiter),
    ):
        return service.increment_naive_client(client_id)

    @app.get("/status")
    async def get_identified_client_status(
        client_id: str = Depends(resolve_client_id),
        service: RateLimiterService = Depends(get_limiter),
    ):
        return service.get_client_status(client_id)

    @app.post("/reset")
    async def reset_identified_client(
        client_id: str = Depends(resolve_client_id),
        service: RateLimiterService = Depends(get_limiter),
    ):
        return service.reset_client(client_id)

    @app.post("/client/{client_id}")
    async def reset_client(
        client_id: str, service: RateLimiterService = Depends(get_limiter)
    ):
        return service.reset_client(client_id)

    @app.post("/client/{client_id}/increment")
    async def increment_client(
        client_id: str, service: RateLimiterService = Depends(get_limiter)
    ):
        return service.increment_client(client_id)

    @app.post("/client/{client_id}/increment/fixed-window")
    async def increment_fixed_window_client(
        client_id: str, service: RateLimiterService = Depends(get_limiter)
    ):
        return service.increment_fixed_window_client(client_id)

    @app.post("/client/{client_id}/increment/naive")
    async def increment_naive_client(
        client_id: str, service: RateLimiterService = Depends(get_limiter)
    ):
        return service.increment_naive_client(client_id)

    @app.get("/client/{client_id}")
    async def get_client(
        client_id: str, service: RateLimiterService = Depends(get_limiter)
    ):
        return service.get_client_status(client_id)

    return app


class UvicornServerThread(threading.Thread):
    def __init__(self, host: str, port: int):
        super().__init__(daemon=True)
        self.host = host
        self.port = port
        self.server: uvicorn.Server | None = None

    def run(self) -> None:
        app = create_app()
        config = uvicorn.Config(app, host=self.host, port=self.port, log_level="warning")
        self.server = uvicorn.Server(config)
        self.server.run()

    def wait_until_started(self, timeout: float = 10.0) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.server and self.server.started:
                return True
            time.sleep(0.05)
        return False

    def stop(self) -> None:
        if self.server is not None:
            self.server.should_exit = True


def run_server(host: str = "0.0.0.0", port: int = 8000) -> None:
    uvicorn.run(create_app(), host=host, port=port)


app = create_app()


if __name__ == "__main__":
    run_server()
