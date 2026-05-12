import os
from dotenv import load_dotenv

load_dotenv()

# ── Telegram ───────────────────────────────────────────────────────────────

BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")

# Bot username without the @ sign, lowercased for easy comparison
BOT_USERNAME: str = os.getenv("BOT_USERNAME", "HuntStatClaudeBot").lower().lstrip("@")

# ── Security ───────────────────────────────────────────────────────────────

# Comma-separated chat IDs, e.g. "-1001234567890,-1009876543210"
_raw_ids = os.getenv("ALLOWED_CHAT_IDS", "")
ALLOWED_CHAT_IDS: list[int] = [
    int(x.strip()) for x in _raw_ids.split(",") if x.strip()
]

# Your personal Telegram user ID — for owner-only commands
_owner_raw = os.getenv("OWNER_USER_ID", "").strip()
OWNER_USER_ID: int = int(_owner_raw) if _owner_raw.lstrip("-").isdigit() else 0

# ── Anthropic ──────────────────────────────────────────────────────────────

ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")

# Claude model to use — override via CLAUDE_MODEL env variable
CLAUDE_MODEL: str = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")

# ── Claude behaviour ───────────────────────────────────────────────────────

# Set to true to save chat messages and pass them to Claude as context (memory)
# Set to false to have Claude answer only the current question with no history
CLAUDE_MEMORY: bool = os.getenv("CLAUDE_MEMORY", "false").lower() == "true"

# How many recent messages to pass to Claude when CLAUDE_MEMORY=true
CONTEXT_MESSAGES: int = int(os.getenv("CONTEXT_MESSAGES", "15"))

# ── Google Sheets ──────────────────────────────────────────────────────────

# ID of the Google Sheet (from the URL)
GOOGLE_SHEET_ID: str = os.getenv("GOOGLE_SHEET_ID", "")

# Path to the service account JSON key file (local development)
GOOGLE_CREDENTIALS_FILE: str = os.getenv("GOOGLE_CREDENTIALS_FILE", "huntstatbot.json")

# On Render/CI: put the entire JSON content in this env variable instead of a file
GOOGLE_CREDENTIALS_JSON: str = os.getenv("GOOGLE_CREDENTIALS_JSON", "")

# ── Validation ─────────────────────────────────────────────────────────────

def validate() -> None:
    """Call once at startup. Raises if required variables are missing."""
    missing = [
        name for name, val in [
            ("BOT_TOKEN", BOT_TOKEN),
            ("ANTHROPIC_API_KEY", ANTHROPIC_API_KEY),
        ]
        if not val
    ]
    if missing:
        raise EnvironmentError(
            f"Missing required environment variables: {', '.join(missing)}\n"
            f"Copy .env.example to .env and fill in the values."
        )
