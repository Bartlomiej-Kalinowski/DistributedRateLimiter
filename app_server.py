import time
from fastapi import FastAPI, HTTPException
from valkey import Valkey
from config import VALKEY_HOST, VALKEY_PORT, MAX_REQUESTS, TIME_WINDOW

app = FastAPI(title="Valkey Rate Limiter API - Sliding Window")

# Połączenie z bazą Valkey w Dockerze
r = Valkey(host=VALKEY_HOST, port=VALKEY_PORT, db=0, decode_responses=True)

# 1. RESET / CZYSZCZENIE stanu klienta
@app.post("/client/{client_id}")
def reset_client(client_id: str):
    # Usuwa klucz (przydatne do czyszczenia starych danych przed testem)
    r.delete(client_id)
    return {"message": "Zresetowano", "client_id": client_id, "requests_numb": 0}

# 2. SLIDING WINDOW (na bazie Sorted Sets)
@app.post("/client/{client_id}/increment")
def increment_client(client_id: str):
    now = time.time()
    window_start = now - TIME_WINDOW

    # Krok 1: Usuń ze zbioru zapytania starsze niż okno czasowe (starsze niż 60s)
    r.zremrangebyscore(client_id, 0, window_start)

    # Krok 2: Policz, ile zapytań znajduje się obecnie w oknie
    current_requests = r.zcard(client_id)

    # Krok 3: Sprawdź, czy limit został już osiągnięty
    if current_requests >= MAX_REQUESTS:
        raise HTTPException(
            status_code=429,
            detail="Przekroczono limit zapytań (Too Many Requests)"
        )

    # Krok 4: Dodaj nowe zapytanie (unikalna nazwa w nanosekundach, waga = czas w sekundach)
    r.zadd(client_id, {str(time.time_ns()): now})

    # Krok 5: Odśwież TTL klucza, aby baza automatycznie posprzątała po nieaktywnym kliencie
    r.expire(client_id, TIME_WINDOW)

    return {
        "message": "Zwiększono",
        "client_id": client_id,
        "requests_numb": current_requests + 1
    }

# 3. GET (sprawdzenie aktualnego stanu w oknie)
@app.get("/client/{client_id}")
def get_client(client_id: str):
    if not r.exists(client_id):
        raise HTTPException(status_code=404, detail="Nie znaleziono klienta")

    # Przed odczytem usuwamy przeterminowane wpisy, aby zwrócić realny stan okna
    now = time.time()
    r.zremrangebyscore(client_id, 0, now - TIME_WINDOW)

    count = r.zcard(client_id)
    ttl = r.ttl(client_id)
    return {"client_id": client_id, "requests_numb": count, "ttl_remaining": ttl}