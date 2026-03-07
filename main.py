"""
Main polling loop — entry point of the CROUS scraper.

Flow:
  1. Load IDF accommodation IDs from idf_accommodations.csv
  2. Every POLL_INTERVAL seconds, hit each ID's direct API endpoint
  3. If one flips to available=True and we haven't seen it before → send email

Prerequisites:
  - Run build_csv.py once to build the full database
  - Run filter_idf.py once to extract IDF-only rooms
  - Fill in .env with your API keys

Run with: python3 main.py
"""
import time
import logging
import sys
from typing import List

from scraper import load_idf_ids, fetch_available_accommodations
from notifier import send_alert
from state import load_seen_ids, save_seen_ids
from config import POLL_INTERVAL
import os

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("crous.log"),
    ],
)
# Silence httpx's per-request HTTP logs — we don't need "GET ... 200 OK" spam
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


def check(idf_rows: List[dict], seen_ids: set) -> set:
    available = fetch_available_accommodations(idf_rows)

    if not available:
        logging.info("Nothing available right now. Patience...")
        save_seen_ids(seen_ids)
        return seen_ids

    new_listings = [item for item in available if str(item.get("id")) not in seen_ids]

    if new_listings:
        logging.info(f"🎉 {len(new_listings)} NEW listing(s) found!")
        for item in new_listings:
            acc_id = str(item.get("id"))
            seen_ids.add(acc_id)
            send_alert(item)
    else:
        logging.info(f"{len(available)} available but all already seen — no new alerts.")

    save_seen_ids(seen_ids)
    return seen_ids


def main():
    logging.info("=== CROUS IDF Scraper started ===")

    idf_rows = load_idf_ids()
    if not idf_rows:
        logging.error("No IDF rows loaded. Run build_csv.py then filter_idf.py first!")
        sys.exit(1)

    logging.info(f"Watching {len(idf_rows)} IDF accommodations.")

    if os.getenv("RESET_STATE", "").lower() == "true":
        logging.info("RESET_STATE=true — clearing seen IDs, will re-alert on all available rooms.")
        seen_ids = set()
        save_seen_ids(seen_ids)
    else:
        seen_ids = load_seen_ids()
        logging.info(f"Loaded {len(seen_ids)} previously seen IDs from state.")

    run_once = os.getenv("RUN_ONCE", "").lower() == "true"
    if run_once:
        logging.info("RUN_ONCE=true — running a single scan and exiting.")
        try:
            check(idf_rows, seen_ids)
        except Exception as e:
            logging.error(f"Unhandled error during single scan: {e}", exc_info=True)
        return

    while True:
        try:
            seen_ids = check(idf_rows, seen_ids)
        except KeyboardInterrupt:
            logging.info("Stopped by user. Bye!")
            break
        except Exception as e:
            logging.error(f"Unhandled error: {e}", exc_info=True)

        logging.info(f"Next scan in {POLL_INTERVAL}s...\n")
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
