# EU Liquidation Radar (Telegram Bot) — v0 (Sneakers)

Scans EU auction/liquidation sites, normalizes listings, estimates margin after fees+shipping, and pings you with top lots. v0 focuses on **sneakers** via 2 sources (Troostwijk, Vavato), hourly digest, and `/watch`.

## Quick start

```bash
pyenv shell 3.11  # or any >=3.10
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Playwright browsers (for sites that render with JS)
python -m playwright install --with-deps

cp .env.example .env  # and edit TELEGRAM_BOT_TOKEN
python main.py
```

Bot will run in long-polling. A minimal FastAPI server exposes `/healthz`.

### Commands
- `/start` — intro + your base location
- `/watch <keywords>` — add a watch (e.g., `/watch nike adidas size 42`)
- `/unwatch` — remove a watch by id
- `/near <radius_km>` — set preferred search radius
- `/top` — top lots from last 24h
- `/help` — list commands

### Notes
- SQLite by default (file `radar.db`). For Postgres, set `DATABASE_URL`.
- Heuristics for **fees** and **shipping** are editable via `.env`.
- Distance computed from your base location (defaults to Marseille).
- Flip score mixes margin %, absolute margin, distance, and recency.

## Deploy
- Systemd or Docker. For webhook deploy, point Telegram webhook to FastAPI `/telegram/webhook` (not required in v0).

## Legal & Ethics
Scraping honors `robots.txt` where appropriate. Use responsibly, respect site ToS.
