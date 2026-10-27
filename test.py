import requests

BASE_URL = "http://localhost:8000"
CLIENT_IP = "127.0.0.1"

print(f"Rozpoczynam test dla IP: {CLIENT_IP}...\n")

# 1. incrementaion
print("Wysyłam zapytanie nr 1 (POST)...")
res1 = requests.post(f"{BASE_URL}/client/{CLIENT_IP}/increment")
print("Odpowiedź:", res1.json())

# 2. incrementation
print("Wysyłam zapytanie nr 2 (POST)...")
res2 = requests.post(f"{BASE_URL}/client/{CLIENT_IP}/increment")
print("Odpowiedź:", res2.json())

# 3. get and verify
print("\nSprawdzam ostateczny wynik w bazie (GET)...")
res_get = requests.get(f"{BASE_URL}/client/{CLIENT_IP}")
dane = res_get.json()

print(f"Dane pobrane z serwera: {dane}")

# test
if dane["requests_numb"] == 2:
    print("Wartość w bazie wynosi dokładnie 2.")
else:
    print(f"Oczekiwano 2, otrzymano {dane['requests_numb']}")