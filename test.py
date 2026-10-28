from collections import Counter
import threading
import time

import requests

from app_server import UvicornServerThread
from config import MAX_REQUESTS

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
    statuses: Counter,
    lock: threading.Lock,
) -> None:
    time.sleep(start_delay)
    for _ in range(requests_count):
        try:
            response = requests.post(
                f"{base_url}/client/{client_id}/increment",
                timeout=2.0,
            )
            with lock:
                statuses[response.status_code] += 1
        except requests.RequestException:
            with lock:
                statuses[-1] += 1
        time.sleep(interval)


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

        # Reset tested client state
        requests.post(f"{base_urls[0]}/client/{CLIENT_ID}", timeout=2.0)

        # Test 404 error for non-existent client
        response_404 = requests.get(
            f"{base_urls[0]}/client/{MISSING_CLIENT_ID}", timeout=2.0
        )
        print(f"GET non-existent client -> HTTP {response_404.status_code}")
        if response_404.status_code != 404:
            raise AssertionError("Expected HTTP 404 for non-existent client.")

        statuses: Counter = Counter()
        lock = threading.Lock() # lock for multithread updates

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
                    statuses,
                    lock,
                ),
            )
            workers.append(worker)
            worker.start() # start the thread with a server

        for worker in workers:
            worker.join()

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