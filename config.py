import os
from datetime import datetime
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

load_dotenv()

# --- CROUS API ---
TOOL_ID = 42
try:
    LOCAL_TIMEZONE = ZoneInfo("Europe/Paris")
except Exception:
    LOCAL_TIMEZONE = datetime.now().astimezone().tzinfo
FAST_SCAN_WEEKDAYS = {1, 3}  # Tuesday, Thursday
FAST_POLL_INTERVAL = 300  # 5 minutes
DEFAULT_POLL_INTERVAL = 900  # 15 minutes


def current_local_time() -> datetime:
    return datetime.now(LOCAL_TIMEZONE)


def is_weekend(now: datetime | None = None) -> bool:
    current = now or current_local_time()
    return current.weekday() >= 5  # Saturday, Sunday


def get_current_poll_interval(now: datetime | None = None) -> int:
    current = now or current_local_time()
    return FAST_POLL_INTERVAL if current.weekday() in FAST_SCAN_WEEKDAYS else DEFAULT_POLL_INTERVAL


# Backward-compatible constant; main loop uses get_current_poll_interval().
POLL_INTERVAL = DEFAULT_POLL_INTERVAL


def _read_str_env(name: str):
    value = os.getenv(name)
    if value is None:
        return None
    value = value.strip()
    return value if value else None


def _read_int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _infer_smtp(sender_email: str):
    if not sender_email or "@" not in sender_email:
        return None, 587, "starttls"

    domain = sender_email.split("@", 1)[1].lower()
    if domain in {"gmail.com", "googlemail.com"}:
        return "smtp.gmail.com", 587, "starttls"
    if domain in {"outlook.com", "hotmail.com", "live.com", "msn.com"}:
        return "smtp.office365.com", 587, "starttls"
    if domain in {"yahoo.com", "yahoo.fr", "ymail.com"}:
        return "smtp.mail.yahoo.com", 587, "starttls"

    return None, 587, "starttls"


# --- Sender/recipients ---
# Defaults requested by user; can still be overridden by env vars.
SENDER_EMAIL = _read_str_env("SENDER_EMAIL") or "outaboo532@gmail.com"
SENDER_NAME = "CROUS Bot"


# --- SMTP email transport ---
# Supported values for SMTP_SECURITY: "starttls", "ssl", "none"
_default_host, _default_port, _default_security = _infer_smtp(SENDER_EMAIL)
SMTP_HOST = _read_str_env("SMTP_HOST") or _default_host
SMTP_PORT = _read_int_env("SMTP_PORT", _default_port)
SMTP_SECURITY = (_read_str_env("SMTP_SECURITY") or _default_security).lower()
SMTP_USERNAME = _read_str_env("SMTP_USERNAME") or SENDER_EMAIL
SMTP_PASSWORD = _read_str_env("SMTP_PASSWORD") or _read_str_env("EMAIL_APP_PASSWORD")

# --- Recipients ---
# Comma-separated list of emails in RECIPIENT_EMAIL env var
# e.g. RECIPIENT_EMAIL=you@gmail.com,friend@gmail.com


def load_recipients() -> list:
    """Load recipient emails from RECIPIENT_EMAIL env var (comma-separated)."""
    value = os.getenv("RECIPIENT_EMAIL", "abderrazzak.outzoula@centrale-casablanca.ma")
    return [e.strip() for e in value.split(",") if e.strip()]


# --- State file (persists seen listing IDs across restarts) ---
STATE_FILE = "seen_ids.json"
