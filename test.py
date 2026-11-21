from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import os
import threading
import time

import requests
from valkey import Valkey

from app_server import UvicornServerThread
from config import MAX_REQUESTS, TIME_WINDOW

HOST = "127.0.0.1"
N_SERVERS = 5
START_PORT = 8100
CLIENT_ID = "127.0.0.1"
MISSING_CLIENT_ID = "client-does-not-exist"
REQUESTS_PER_SERVER = 40

# Various start delays and intervals (seconds/milliseconds)
START_DELAYS = [0.0, 0.25, 0.5, 0.75, 1.1]
REQUEST_INTERVALS = [0.005, 0.007, 0.004, 0.006, 0.005]


def wait_for_server(base_url: str, timeout: float = 10.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            response = requests.get(f"{base_url}/docs", timeout=1.0)
            if response.status_code == 200:
                return True
        except requests.RequestException:
            pass
        time.sleep(0.1)
    return False


def request_sender(
    base_url: str,
    client_id: str,
    start_delay: float,
    interval: float,
    requests_count: int,
    worker_result: list[Counter],
    worker_client_values: list[list[int]],
    in_flight_state: dict[str, int],
    in_flight_lock: threading.Lock,
    worker_index: int,
) -> None:
    local_statuses: Counter = Counter()
    local_client_values: list[int] = []
    time.sleep(start_delay)
    for _ in range(requests_count):
        with in_flight_lock:
            in_flight_state["count"] += 1
            in_flight_count = in_flight_state["count"]

        try:
            response = requests.post(
                f"{base_url}/client/{client_id}/increment",
                timeout=2.0,
            )
            local_statuses[response.status_code] += 1
            if response.status_code == 200:
                payload = response.json()
                value = payload.get("requests_numb")
                if isinstance(value, int):
                    local_client_values.append(value)
                    if in_flight_count == 1:
                        print(
                            f"[Lua queue size=1] client_id='{client_id}', requests_numb={value}, server={base_url}"
                        )
                    else:
                        print(
                            f"\t[Lua queue size>1] waiting scripts detected ({in_flight_count}) "
                            f"client_id='{client_id}', requests_numb={value}, server={base_url}"
                        )
        except requests.RequestException:
            local_statuses[-1] += 1
        finally:
            with in_flight_lock:
                in_flight_state["count"] -= 1
        time.sleep(interval)
    worker_result[worker_index] = local_statuses
    worker_client_values[worker_index] = local_client_values


def run_fixed_window_test(base_urls: list[str]) -> None:
    client_id = f"{CLIENT_ID}-fixed-window"
    reset_response = requests.post(
        f"{base_urls[0]}/client/{client_id}", timeout=2.0
    )
    if reset_response.status_code != 200:
        raise AssertionError("Could not reset fixed-window test client.")

    for request_number in range(1, MAX_REQUESTS + 1):
        base_url = base_urls[(request_number - 1) % len(base_urls)]
        response = requests.post(
            f"{base_url}/client/{client_id}/increment/fixed-window",
            timeout=2.0,
        )
        if response.status_code != 200:
            raise AssertionError(
                f"Fixed-window request {request_number} was rejected: HTTP {response.status_code}."
            )

        payload = response.json()
        if payload.get("requests_numb") != request_number:
            raise AssertionError("Fixed-window counter did not increment correctly.")
        ttl = payload.get("ttl_remaining")
        if not isinstance(ttl, int) or not 1 <= ttl <= TIME_WINDOW:
            raise AssertionError(f"Fixed-window TTL is invalid: {ttl}.")

    rejected_response = requests.post(
        f"{base_urls[-1]}/client/{client_id}/increment/fixed-window",
        timeout=2.0,
    )
    if rejected_response.status_code != 429:
        raise AssertionError("Fixed-window limit was not enforced across servers.")

    reset_response = requests.post(
        f"{base_urls[0]}/client/{client_id}", timeout=2.0
    )
    if reset_response.status_code != 200:
        raise AssertionError("Could not reset fixed-window test client.")

    reset_response = requests.post(
        f"{base_urls[-1]}/client/{client_id}/increment/fixed-window",
        timeout=2.0,
    )
    if (
        reset_response.status_code != 200
        or reset_response.json().get("requests_numb") != 1
    ):
        raise AssertionError("Fixed-window counter was not reset correctly.")

    print(
        f"Fixed-window test passed: {MAX_REQUESTS} requests allowed across servers, "
        "the next was rejected, TTL was set, and reset succeeded."
    )


def run_naive_test(base_urls: list[str]) -> None:
    client_id = f"{CLIENT_ID}-naive"
    reset_response = requests.post(
        f"{base_urls[0]}/client/{client_id}", timeout=2.0
    )
    if reset_response.status_code != 200:
        raise AssertionError("Could not reset naive test client.")

    def send_request(request_number: int) -> int:
        base_url = base_urls[request_number % len(base_urls)]
        try:
            response = requests.post(
                f"{base_url}/client/{client_id}/increment/naive", timeout=10.0
            )
            return response.status_code
        except requests.RequestException:
            return -1

    total_requests = N_SERVERS * REQUESTS_PER_SERVER
    with ThreadPoolExecutor(max_workers=total_requests) as executor:
        statuses = Counter(executor.map(send_request, range(total_requests)))

    status_summary = {200: statuses[200], 429: statuses[429]}
    print(f"Naive response statuses: {status_summary}")
    extra_allowed = max(0, statuses[200] - MAX_REQUESTS)
    print(f"Naive requests allowed beyond MAX_REQUESTS={MAX_REQUESTS}: {extra_allowed}")

    if statuses[200] < MAX_REQUESTS:
        raise AssertionError(
            f"Naive limiter allowed only {statuses[200]} requests; expected at least {MAX_REQUESTS}."
        )

    host = os.getenv("VALKEY_HOST", "localhost")
    port = int(os.getenv("VALKEY_PORT", 6379))
    db = Valkey(host=host, port=port, db=0, decode_responses=True)
    final_counter = db.get(f"naive:{client_id}")
    print(f"Final naive Valkey counter: {final_counter}")


def run_distributed_test() -> None:
    ports = [START_PORT + i for i in range(N_SERVERS)] # list of ports for app1..n
    base_urls = [f"http://{HOST}:{port}" for port in ports] # URL for app ports above

    servers = [UvicornServerThread(HOST, port) for port in ports] # servers app1..n
    for server in servers:# start all servers
        server.start()

    try:
        for base_url, server in zip(base_urls, servers):
            if not server.wait_until_started() or not wait_for_server(base_url): # checks if server is ready
                raise RuntimeError(f"Server failed to start properly: {base_url}")

        print(f"Started {N_SERVERS} application servers on ports: {ports}")
        run_fixed_window_test(base_urls)
        run_naive_test(base_urls)

        # Reset tested client state
        requests.post(f"{base_urls[0]}/client/{CLIENT_ID}", timeout=2.0)

        # Test 404 error for non-existent client
        response_404 = requests.get(
            f"{base_urls[0]}/client/{MISSING_CLIENT_ID}", timeout=2.0
        )
        print(f"GET non-existent client -> HTTP {response_404.status_code}")
        if response_404.status_code != 404:
            raise AssertionError("Expected HTTP 404 for non-existent client.")

        worker_result: list[Counter] = [Counter() for _ in range(N_SERVERS)]
        worker_client_values: list[list[int]] = [[] for _ in range(N_SERVERS)]
        in_flight_state = {"count": 0}
        in_flight_lock = threading.Lock()

        workers: list[threading.Thread] = [] # list of threads sending requests
        for i in range(N_SERVERS): # each thread for each server app1..n
            worker = threading.Thread(
                target=request_sender,
                args=(
                    base_urls[i],
                    CLIENT_ID,
                    START_DELAYS[i],
                    REQUEST_INTERVALS[i],
                    REQUESTS_PER_SERVER,
                    worker_result,
                    worker_client_values,
                    in_flight_state,
                    in_flight_lock,
                    i,
                ),
            )
            workers.append(worker)
            worker.start() # start the thread with a server

        for worker in workers:
            worker.join()

        statuses: Counter = Counter()
        for local_statuses in worker_result:
            statuses.update(local_statuses)

        total_requests = N_SERVERS * REQUESTS_PER_SERVER # how many requests was sent totally by all servers
        print(f"Sent a total of {total_requests} requests across 5 servers.")
        print(f"Response statuses: {dict(statuses)}")

        if statuses[429] == 0:
            raise AssertionError("HTTP 429 was not detected; rate limit was not exceeded.")

        final_response = requests.get(f"{base_urls[0]}/client/{CLIENT_ID}", timeout=2.0)
        print(f"Final client state -> HTTP {final_response.status_code}")
        if final_response.status_code == 200:
            print(f"Client data: {final_response.json()}")

        print(
            "Test completed: rate limits (429) detected and 404 error confirmed."
        )
        print(f"MAX_REQUESTS={MAX_REQUESTS}, requests per test={total_requests}")
    finally:
        for server in servers:
            server.stop()
        for server in servers:
            server.join(timeout=5.0)


if __name__ == "__main__":
    run_distributed_test()
