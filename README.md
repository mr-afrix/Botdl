# SAGE BOT

Powerful Telegram bot powered by SAGE APIs (275+ endpoints). Downloads, search, tools, stalk, fun, crypto.

## Commands

Music / Video:
- `/song <name>`, `/play <name>`, `/video <name>`
- `/ytmp3 <url>`, `/ytmp4 <url>`, `/yts <query>`
- `/lyrics <song>`, `/spotify <url>`, `/soundcloud <url>`

Social downloads:
- `/ig <url>`, `/tiktok <url>`, `/fb <url>`, `/twitter <url>`, `/pinterest <url>`

Search:
- `/google <q>`, `/image <q>`, `/news <q>`, `/movie <q>`, `/wiki <q>`
- `/ghsearch <q>`, `/so <q>`, `/npm <q>`

Tools:
- `/qr <text>`, `/shorten <url>`, `/weather <city>`, `/translate <to> <text>`
- `/ip <ip>`, `/dns <domain>`, `/whois <domain>`, `/ssl <domain>`
- `/password [len]`, `/uuid`, `/hash <text>`, `/country <name>`, `/currency <amt> <from> <to>`, `/myip`

Stalk:
- `/ghuser <username>`, `/igstalk <username>`, `/ttstalk <username>`
- `/ytstalk <channel>`, `/twstalk <username>`

Fun / Games / Crypto:
- `/joke`, `/quote`, `/fact`, `/meme`, `/trivia`, `/coinflip`, `/dice [sides]`, `/8ball <q>`, `/trending`

## Local run

```bash
pip install -r requirements.txt
export BOT_TOKEN=your_token
python bot.py
```

## Deploy on Render

1. Push this repo to GitHub.
2. New → Blueprint → connect repo. Render reads `render.yaml`.
3. Set `BOT_TOKEN` env var. Deploy. Runs as background worker (no port needed).

## Deploy on Railway

1. New Project → Deploy from GitHub repo.
2. Railway auto-detects `nixpacks.toml` / `railway.json`.
3. Add `BOT_TOKEN` in Variables (and optionally `API_KEY`, `BASE_URL`). Deploy.

## Docker

```bash
docker build -t sage-bot .
docker run -e BOT_TOKEN=xxx sage-bot
```
