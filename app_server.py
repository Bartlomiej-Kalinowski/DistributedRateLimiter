from fastapi import FastAPI, HTTPException
from valkey import Valkey

app = FastAPI(title="Valkey Rate Limiter API")

# connection with Valkey database in Docker
# name valkey-db is defined in yml file
r = Valkey(host='valkey-db', port=6379, db=0, decode_responses=True)

# 1. ADD / SET values
@app.post("/client/{client_id}")
def set_client(client_id: str, value: int = 0):
    # set value
    r.set(client_id, value)
    return {"message": "Zapisano", "client_id": client_id, "requests_numb": value}

# 2. incrementation
@app.post("/client/{client_id}/increment")
def increment_client(client_id: str):
    # r.increment = value+=1
    # if key does not exist, it will be created and initialized with 0, then incremented
    new_value = r.incr(client_id)
    return {"message": "Zwiększono", "client_id": client_id, "requests_numb": new_value}

# 3. GET
@app.get("/client/{client_id}")
def get_client(client_id: str):
    value = r.get(client_id)
    if value is None:
        raise HTTPException(status_code=404, detail="Nie znaleziono klienta")
    return {"client_id": client_id, "requests_numb": int(value)}