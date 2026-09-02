# mapGen

Webowy generator map Plemiona.pl / Tribal Wars. Aplikacja pobiera dane wybranego
swiata przy pierwszym uzyciu i przechowuje je lokalnie w katalogu `data/`.

## Uruchomienie lokalne

```bash
uv sync
uv run mapgen-web
```

Otworz `http://127.0.0.1:5000/`.

## Hosting na Render

1. Wypchnij repozytorium na GitHub.
2. W Render wybierz **New > Blueprint** i wskaz to repozytorium.
3. Render odczyta `render.yaml`, zainstaluje zaleznosci i uruchomi aplikacje.
4. Otworz wygenerowany adres `https://...onrender.com`.

Pierwsze wygenerowanie mapy dla danego swiata pobiera pliki z serwera gry, wiec
moze potrwac kilkanascie sekund. Darmowa usluga Render usypia aplikacje po
bezczynnosci, a pobrane pliki sa cache'em i moga zostac usuniete po restarcie.
