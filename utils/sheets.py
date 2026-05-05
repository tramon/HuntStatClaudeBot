"""
Google Sheets storage for hunt session stats.

Sheet name: Sessions
Columns:    Date | Won | Total | Win % | Server Wipes

Credentials priority:
  1. GOOGLE_CREDENTIALS_JSON env var (JSON string) — used on Render/CI
  2. GOOGLE_CREDENTIALS_FILE path — used locally
"""

import json
import logging
from datetime import date

import gspread
from google.oauth2.service_account import Credentials

import config

logger = logging.getLogger(__name__)

SHEET_NAME = "Sessions"
HEADERS = ["Date", "Won", "Total", "Win %", "Server Wipes"]
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

_client: gspread.Client | None = None


def _get_client() -> gspread.Client:
    global _client
    if _client is not None:
        return _client

    if config.GOOGLE_CREDENTIALS_JSON:
        info = json.loads(config.GOOGLE_CREDENTIALS_JSON)
        creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    else:
        creds = Credentials.from_service_account_file(
            config.GOOGLE_CREDENTIALS_FILE, scopes=SCOPES
        )

    _client = gspread.authorize(creds)
    return _client


def _get_sheet() -> gspread.Worksheet:
    """Open the spreadsheet and return the Sessions worksheet."""
    client = _get_client()
    spreadsheet = client.open_by_key(config.GOOGLE_SHEET_ID)

    try:
        ws = spreadsheet.worksheet(SHEET_NAME)
    except gspread.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(title=SHEET_NAME, rows=1000, cols=5)
        ws.append_row(HEADERS)
        logger.info(f"Created '{SHEET_NAME}' worksheet with headers")

    return ws


# ── Public API ─────────────────────────────────────────────────────────────

def append_session(won: int, total: int, wipes: int = 0) -> None:
    """Append a new session row to Google Sheets."""
    ws = _get_sheet()
    win_pct = round(won / total * 100) if total > 0 else 0
    today = date.today().isoformat()

    ws.append_row([today, won, total, win_pct, wipes])
    logger.info(f"Session saved: {won}/{total} ({win_pct}%), wipes={wipes} on {today}")


def get_all_sessions() -> list[dict]:
    """Return all sessions as a list of dicts."""
    ws = _get_sheet()
    rows = ws.get_all_values()

    if len(rows) <= 1:
        return []

    sessions = []
    for row in rows[1:]:  # skip header
        if len(row) < 3:
            continue
        date_val = row[0]
        won_raw = row[1]
        total_raw = row[2]
        wipes_raw = row[4] if len(row) > 4 else "0"

        if not won_raw or not total_raw:
            continue
        try:
            won = int(won_raw)
            total = int(total_raw)
            wipes = int(wipes_raw) if wipes_raw else 0
            win_pct = round(won / total * 100) if total > 0 else 0
            sessions.append({
                "date": str(date_val)[:10],
                "won": won,
                "total": total,
                "win_pct": win_pct,
                "wipes": wipes,
            })
        except (ValueError, ZeroDivisionError):
            continue

    return sessions
