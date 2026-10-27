import requests
import time
from config import BASE_URL, MAX_REQUESTS, TIME_WINDOW

CLIENT_IP = "127.0.0.1"

print(f"Rozpoczynam test Sliding Window dla IP: {CLIENT_IP}...\n")

# 0. Czyszczenie starego klucza w bazie przed rozpoczęciem testu
requests.post(f"{BASE_URL}/client/{CLIENT_IP}")
print("Wyczyszczono poprzedni stan klienta w bazie.\n")

# 1. Test przekroczenia limitu
print(f"Wysyłam {MAX_REQUESTS + 2} zapytań, aby wymusić błąd 429...")
for i in range(1, MAX_REQUESTS + 3):
    res = requests.post(f"{BASE_URL}/client/{CLIENT_IP}/increment")

    if res.status_code == 429:
        print(f"Zapytanie nr {i}: ZABLOKOWANE (429 Too Many Requests)")
    elif i == 1 or i == MAX_REQUESTS:
        print(f"Zapytanie nr {i}: {res.json()}")

# 2. Pobranie i weryfikacja stanu
print("\nSprawdzam ostateczny wynik w bazie (GET)...")
res_get = requests.get(f"{BASE_URL}/client/{CLIENT_IP}")
dane = res_get.json()
print(f"Dane pobrane z serwera: {dane}")

# 3. Test wygaśnięcia okna czasowego
print(f"\nCzekam {TIME_WINDOW + 1} sekund na przesunięcie okna czasowego...")
time.sleep(TIME_WINDOW + 1)

print("\nWysyłam nowe zapytanie po upływie czasu okna...")
res_after_wait = requests.post(f"{BASE_URL}/client/{CLIENT_IP}/increment")
print(f"Odpowiedź: {res_after_wait.json()}")

if res_after_wait.status_code == 200 and res_after_wait.json()["requests_numb"] == 1:
    print("Test zaliczony: Okno czasowe przesunęło się i licznik wynosi 1.")
else:
    print("Test nieudany: Limit nie został wyzerowany.")