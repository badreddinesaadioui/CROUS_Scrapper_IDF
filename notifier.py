"""
Sends email notifications via standard SMTP (Gmail/Outlook/other providers).
"""
import logging
import smtplib
import ssl
from email.message import EmailMessage
from typing import List

from config import (
    SMTP_HOST,
    SMTP_PORT,
    SMTP_SECURITY,
    SMTP_USERNAME,
    SMTP_PASSWORD,
    POLL_INTERVAL,
    SENDER_EMAIL,
    SENDER_NAME,
    load_recipients,
)


def _extract_listing(item: dict) -> dict:
    residence = item.get("residence", {})
    name = item.get("label", residence.get("label", "N/A"))
    address = residence.get("address", "N/A")
    listing_url = item.get("url", "https://trouverunlogement.lescrous.fr/")

    occupation_modes = item.get("occupationModes", [])
    rents = []
    mode_types = []
    for mode in occupation_modes:
        mode_types.append(mode.get("type", ""))
        rent = mode.get("rent", {})
        if rent.get("min"):
            rents.append(rent["min"] / 100)
        if rent.get("max"):
            rents.append(rent["max"] / 100)
    rent_str = f"{min(rents):.0f}-{max(rents):.0f} EUR/month" if rents else "N/A"
    modes_str = ", ".join(mode_types) if mode_types else "N/A"

    area = item.get("area", {})
    area_str = f"{area.get('min', '?')}-{area.get('max', '?')} m2"

    return {
        "name": name,
        "address": address,
        "rent": rent_str,
        "area": area_str,
        "type": modes_str,
        "url": listing_url,
    }


def _build_batch_html(items: List[dict]) -> str:
    interval_minutes = max(1, POLL_INTERVAL // 60)
    if not items:
        return f"""
        <html>
        <body style="font-family: Arial, sans-serif; padding: 20px; color: #333;">
            <h2 style="color: #e63946;">CROUS update ({interval_minutes} min)</h2>
            <p><strong>Pas de logement dispo.</strong></p>
            <p style="color: #888; font-size: 12px;">Sent by your CROUS scraper bot.</p>
        </body>
        </html>
        """

    rows = []
    for item in items:
        listing = _extract_listing(item)
        rows.append(
            (
                "<tr>"
                f"<td style='padding:8px; border-bottom:1px solid #eee;'>{listing['name']}</td>"
                f"<td style='padding:8px; border-bottom:1px solid #eee;'>{listing['rent']}</td>"
                f"<td style='padding:8px; border-bottom:1px solid #eee;'>{listing['area']}</td>"
                f"<td style='padding:8px; border-bottom:1px solid #eee;'>{listing['type']}</td>"
                f"<td style='padding:8px; border-bottom:1px solid #eee;'>{listing['address']}</td>"
                f"<td style='padding:8px; border-bottom:1px solid #eee;'><a href='{listing['url']}'>Open</a></td>"
                "</tr>"
            )
        )

    rows_html = "\n".join(rows)
    return f"""
    <html>
    <body style="font-family: Arial, sans-serif; padding: 20px; color: #333;">
        <h2 style="color: #e63946;">CROUS: {len(items)} new listing(s) in the last {interval_minutes} minutes</h2>
        <table style="border-collapse: collapse; width: 100%; font-size: 14px;">
            <thead>
                <tr style="background: #f6f6f6;">
                    <th style="padding: 8px; text-align: left;">Residence</th>
                    <th style="padding: 8px; text-align: left;">Rent</th>
                    <th style="padding: 8px; text-align: left;">Area</th>
                    <th style="padding: 8px; text-align: left;">Type</th>
                    <th style="padding: 8px; text-align: left;">Address</th>
                    <th style="padding: 8px; text-align: left;">Link</th>
                </tr>
            </thead>
            <tbody>
                {rows_html}
            </tbody>
        </table>
        <p style="color: #888; font-size: 12px; margin-top: 16px;">
            Sent by your CROUS scraper bot.
        </p>
    </body>
    </html>
    """


def _build_message(items: List[dict], recipients: List[str]) -> EmailMessage:
    interval_minutes = max(1, POLL_INTERVAL // 60)
    msg = EmailMessage()
    msg["From"] = f"{SENDER_NAME} <{SENDER_EMAIL}>"
    msg["To"] = ", ".join(recipients)
    if items:
        msg["Subject"] = f"CROUS alert: {len(items)} new listing(s)"
        lines = [f"New CROUS listings detected in the last {interval_minutes} minutes:", ""]
        for item in items:
            listing = _extract_listing(item)
            lines.append(f"- {listing['name']} ({listing['rent']})")
            lines.append(f"  {listing['url']}")
        msg.set_content("\n".join(lines))
    else:
        msg["Subject"] = "CROUS update: pas de logement dispo"
        msg.set_content(f"Pas de logement dispo sur les {interval_minutes} dernieres minutes.")

    msg.add_alternative(_build_batch_html(items), subtype="html")
    return msg


def _missing_smtp_config() -> bool:
    required = {
        "SMTP_HOST": SMTP_HOST,
        "SMTP_PORT": SMTP_PORT,
        "SMTP_USERNAME": SMTP_USERNAME,
        "SMTP_PASSWORD": SMTP_PASSWORD,
        "SENDER_EMAIL": SENDER_EMAIL,
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        logging.error(
            "SMTP config missing: %s. Set them in .env or GitHub Secrets.",
            ", ".join(missing),
        )
        return True
    return False


def _open_smtp():
    security = SMTP_SECURITY
    if security not in {"starttls", "ssl", "none"}:
        logging.warning("Unknown SMTP_SECURITY='%s'. Falling back to starttls.", security)
        security = "starttls"

    if security == "ssl":
        return smtplib.SMTP_SSL(
            SMTP_HOST,
            SMTP_PORT,
            timeout=30,
            context=ssl.create_default_context(),
        )

    client = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30)
    if security == "starttls":
        client.starttls(context=ssl.create_default_context())
    return client


def send_alerts(items: List[dict]) -> bool:
    recipients = load_recipients()
    if not recipients:
        logging.error("No recipients configured. Set RECIPIENT_EMAIL in .env.")
        return False
    if _missing_smtp_config():
        return False

    msg = _build_message(items, recipients)
    try:
        with _open_smtp() as client:
            client.login(SMTP_USERNAME, SMTP_PASSWORD)
            client.send_message(msg)
        if items:
            logging.info(
                "Batch email sent for %d new listing(s) -> %s",
                len(items),
                ", ".join(recipients),
            )
        else:
            logging.info("Status email sent (pas de logement dispo) -> %s", ", ".join(recipients))
        return True
    except Exception as e:
        logging.error("Unexpected SMTP error while sending batch email: %s", e)
        return False


def send_alert(item: dict) -> bool:
    # Backward-compatible wrapper.
    return send_alerts([item])
