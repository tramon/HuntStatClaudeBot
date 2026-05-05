# HuntStatClaudeBot

A private Telegram bot for a hunting game group. Logs session results to Google Sheets and answers questions via Claude AI.

## Features

- `/log 6/12` — log a session (won / total missions)
- `/log 6/12/1` — log a session with server wipes
- `/stats` — show aggregate stats from Google Sheets
- `@HuntStatClaudeBot <question>` — ask Claude anything
- `@HuntStatClaudeBot` — show menu buttons

## Setup

### 1. Clone the repo
```
git clone https://github.com/tramon/HuntStatClaudeBot.git
cd HuntStatClaudeBot
```

### 2. Install dependencies
```
pip install -r requirements.txt
```

### 3. Configure environment
```
cp .env.example .env
```
Fill in all values in `.env` (see comments in the file).

### 4. Google Sheets credentials
- Create a Google Cloud project
- Enable Google Sheets API and Google Drive API
- Create a Service Account and download the JSON key
- Place the JSON file in the project folder
- Share your Google Sheet with the service account email

### 5. Run
```
python bot.py
```

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `BOT_TOKEN` | ✅ | Telegram bot token from @BotFather |
| `ANTHROPIC_API_KEY` | ✅ | Anthropic API key |
| `GOOGLE_SHEET_ID` | ✅ | Google Sheet ID from the URL |
| `ALLOWED_CHAT_IDS` | recommended | Comma-separated group chat IDs |
| `CLAUDE_MEMORY` | no | `true` to give Claude chat context (default: `false`) |
| `GOOGLE_CREDENTIALS_FILE` | local | Path to service account JSON file |
| `GOOGLE_CREDENTIALS_JSON` | Render/CI | Full JSON content of credentials file |
