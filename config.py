import os
from dotenv import load_dotenv

load_dotenv()

# --- CROUS API ---
TOOL_ID = 42
POLL_INTERVAL = 60  # seconds between each full scan of IDF accommodations

# --- Brevo ---
BREVO_API_KEY = os.getenv("BREVO_API_KEY")
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_NAME = "CROUS Bot"

# --- Recipients ---
# Comma-separated list of emails in RECIPIENT_EMAIL env var
# e.g. RECIPIENT_EMAIL=you@gmail.com,friend@gmail.com


def load_recipients() -> list:
    """Load recipient emails from RECIPIENT_EMAIL env var (comma-separated)."""
    value = os.getenv("RECIPIENT_EMAIL", "")
    return [e.strip() for e in value.split(",") if e.strip()]


# --- State file (persists seen listing IDs across restarts) ---
STATE_FILE = "seen_ids.json"
