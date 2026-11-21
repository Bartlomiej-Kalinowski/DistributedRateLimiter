1. Główna implementacja
[x] Instancje aplikacji odbierające żądania: Dodać obsługę z nagłówka X-API-Key lub IP jako alternatywę dla obecnego client_id w ścieżce.

[x] Licznik stałego okna (fixed-window): Prosta implementacja z użyciem wygasania (TTL).

[x] Licznik przesuwnego okna (sliding-window): Wykorzystanie posortowanych zbiorów (sorted sets) w Valkey.

[x] Globalne reguły ograniczania: Wymuszanie limitu (np. 100 żądań / 60s) współdzielonego przez wszystkie serwery.

[x] Decyzje atomowe: Użycie operacji atomowych Valkey, transakcji lub skryptów Lua.

[x] Implementacja naiwna (nieatomowa): Sekwencja np. GET, inkrementacja, SET w celach porównawczych.

2. Rozproszona infrastruktura Valkey
[ ] Wdrożenie klastra Valkey: Partycjonowanie i replikacja: min. 3 węzły primary i 3 repliki. Nie używać samego Sentinela.

[ ] Badanie Hash Slots i kluczy: Wskazać, gdzie trafiają klucze (rate:client:A, B, C) i opisać wpływ na lokalność danych.

[ ] Zastosowanie Hash Tags: Zastosować (np. rate:{client_id}:window) dla operacji wielokluczowych lub udokumentować ich brak.

[ ] Instrukcja odtworzenia środowiska: Jasne kroki uruchomienia klastra i weryfikacji jego stanu.

3. Eksperymenty i testy
[ ] [DO WERYFIKACJI] Test żądań współbieżnych: Potwierdzenie ścisłego egzekwowania globalnego limitu z wielu instancji aplikacji.

[ ] Test awarii węzła (Node failure): Zatrzymać węzeł Valkey z licznikiem, zmierzyć czas przywracania i obsługę żądań.

[ ] Zachowanie przy niedostępności (fail-open/closed): Udokumentować i przetestować przepuszczanie (open) lub blokowanie (closed) żądań przy awarii.

[ ] Test współbieżności i atomowości: Setki jednoczesnych żądań – porównanie implementacji naiwnej z atomową.

[ ] Test wolnych/przeciążonych komponentów: Kontrolowane opóźnienie Valkey/App – pomiar timeoutów, opóźnień i nieudanych żądań.

[ ] Test replikacji (Replication failure): Zabić węzeł primary tuż po aktualizacji stanu. Sprawdzić, czy najnowszy stan jest widoczny.

[ ] Test podziału sieci (Network partition): Tymczasowo odłączyć węzeł Valkey. Zbadać dostępność i spójność po wznowieniu.

[ ] Test skalowania: Porównanie 1 instancji Valkey z klastrem przy rosnącym ruchu i liczbie klientów.

[ ] Detekcja nadużyć (Abuse detection): Oznaczanie/rejestrowanie w logach klientów powtarzających naruszenia limitów.

[ ] Zarejestrowanie głównych metryk: Przepustowość, opóźnienie decyzji, dokładność limitów, liczba błędów, recovery time.

4. Końcowe rezultaty i dokumentacja
[ ] Przygotowanie kodu źródłowego: Kod musi być skomentowany, przetestowany i odporny na natychmiastowe crashe.

[ ] Raport końcowy (~10 stron): Architektura, implementacja, wyniki testów, analiza współbieżności i awarii oraz wkład każdej osoby.

[ ] Learning Outcomes w raporcie: Zawarć analizę: replikacji, shardingu, atomowości, spójności vs dostępności, fault tolerance i TTL.

[ ] Dokumentacja na GitHub: Diagram sekwencji podstawowej sesji oraz diagram docelowej architektury oprogramowania.

[ ] Plan inkrementów i biblioteki (GitHub): Opis kroków pośrednich (increments), testów oraz krótki opis wykorzystanych bibliotek.

[ ] Demonstracja na żywo (Live Demo): Działanie systemu min. 3 aplikacji z klastrem. Globalny limit działa niezależnie od węzła.

[ ] Scenariusz awarii na żywo: Zademonstrowanie niedostępności węzła Valkey i zachowania (fail-open/closed).

5. Wymagania organizacyjne i inżynieryjne

[ ] Obowiązkowo subskrypcja/dostęp dla użytkownika andrzej-duda.

[ ] Konto chmurowe: Założyć darmowe konto na Azure, IBM lub Amazon dla projektu.

[ ] Debugging i Logowanie: Logi ze sterowanym poziomem (np. log4j) i zachowany ślad wykonania od początku projektu.

[ ] Nieblokujące/asynchroniczne I/O: Zweryfikować wywołania klienta Valkey w FastAPI; użyć klienta async lub bezpiecznej puli wątków dla obciążenia.