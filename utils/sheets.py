"""
Google Sheets storage for hunt session stats.

Sheet name: Sessions
Columns:    Date | Won | Total | Win % | Server Wipes

Credentials priority:
  1. GOOGLE_CREDENTIALS_JSON env var (JSON string) -- used on Render/CI
  2. GOOGLE_CREDENTIALS_FILE path -- used locally
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

_client = None


class SheetsError(Exception):
    """Raised when a Google Sheets operation fails."""
    pass


def _get_client():
    global _client
    if _client is not None:
        return _client

    try:
        if config.GOOGLE_CREDENTIALS_JSON:
            info = json.loads(config.GOOGLE_CREDENTIALS_JSON)
            creds = Credentials.from_service_account_info(info, scopes=SCOPES)
        else:
            creds = Credentials.from_service_account_file(
                config.GOOGLE_CREDENTIALS_FILE, scopes=SCOPES
            )
        _client = gspread.authorize(creds)
        return _client
    except FileNotFoundError:
        logger.error(f"Credentials file not found: {config.GOOGLE_CREDENTIALS_FILE}")
        raise SheetsError("Credentials file not found. Check GOOGLE_CREDENTIALS_FILE.")
    except (json.JSONDecodeError, KeyError) as e:
        logger.error(f"Invalid credentials JSON: {e}")
        raise SheetsError("Credentials JSON is invalid. Check GOOGLE_CREDENTIALS_JSON.")
    except Exception as e:
        logger.error(f"Failed to authenticate with Google: {e}")
        raise SheetsError(f"Google auth failed: {e}")


def _get_sheet():
    """Open the spreadsheet and return the Sessions worksheet."""
    try:
        client = _get_client()
        spreadsheet = client.open_by_key(config.GOOGLE_SHEET_ID)
    except SheetsError:
        raise
    except gspread.exceptions.APIError as e:
        logger.error(f"Sheets API error: {e}")
        raise SheetsError("Cannot access Google Sheet. Check GOOGLE_SHEET_ID and sharing.")
    except Exception as e:
        logger.error(f"Error opening spreadsheet: {e}")
        raise SheetsError(f"Cannot open spreadsheet: {e}")

    try:
        ws = spreadsheet.worksheet(SHEET_NAME)
    except gspread.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(title=SHEET_NAME, rows=1000, cols=5)
        ws.append_row(HEADERS)
        logger.info(f"Created '{SHEET_NAME}' worksheet with headers")

    return ws


def append_session(won, total, wipes=0):
    """Append a new session row to Google Sheets."""
    try:
        ws = _get_sheet()
        win_pct = round(won / total * 100) if total > 0 else 0
        today = date.today().isoformat()
        ws.append_row([today, won, total, win_pct, wipes])
        logger.info(f"Session saved: {won}/{total} ({win_pct}%), wipes={wipes} on {today}")
    except SheetsError:
        raise
    except Exception as e:
        logger.error(f"Failed to save session: {e}")
        raise SheetsError(f"Failed to save session: {e}")


def get_all_sessions():
    """Return all sessions as a list of dicts."""
    try:
        ws = _get_sheet()
        rows = ws.get_all_values()
    except SheetsError:
        raise
    except Exception as e:
        logger.error(f"Failed to read from Sheets: {e}")
        raise SheetsError(f"Failed to read data: {e}")

    if len(rows) <= 1:
        return []

    sessions = []
    for row in rows[1:]:
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
