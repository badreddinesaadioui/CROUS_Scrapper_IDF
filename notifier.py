"""
Sends email notifications via standard SMTP (Gmail/Outlook/other providers).
"""
import logging
import smtplib
import ssl
from email.message import EmailMessage

from config import (
    SMTP_HOST,
    SMTP_PORT,
    SMTP_SECURITY,
    SMTP_USERNAME,
    SMTP_PASSWORD,
    SENDER_EMAIL,
    SENDER_NAME,
    load_recipients,
)


def build_html(item: dict) -> str:
    # Residence info is nested
    residence = item.get("residence", {})
    name = item.get("label", residence.get("label", "N/A"))
    address = residence.get("address", "N/A")
    listing_url = item.get("url", "https://trouverunlogement.lescrous.fr/")

    # Rent: API returns cents, convert to euros
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

    # Equipment
    equipments = item.get("equipments", [])
    equip_str = ", ".join(e.get("label", "") for e in equipments) if equipments else "N/A"

    # Area
    area = item.get("area", {})
    area_str = f"{area.get('min', '?')}-{area.get('max', '?')} m2"

    return f"""
    <html>
    <body style="font-family: Arial, sans-serif; padding: 20px; color: #333; max-width: 600px;">
        <h2 style="color: #e63946;">CROUS room just dropped!</h2>
        <table style="border-collapse: collapse; width: 100%;">
            <tr>
                <td style="padding: 8px; font-weight: bold; width: 140px;">Residence</td>
                <td style="padding: 8px;">{name}</td>
            </tr>
            <tr style="background: #f4f4f4;">
                <td style="padding: 8px; font-weight: bold;">Address</td>
                <td style="padding: 8px;">{address}</td>
            </tr>
            <tr>
                <td style="padding: 8px; font-weight: bold;">Rent</td>
                <td style="padding: 8px;">{rent_str}</td>
            </tr>
            <tr style="background: #f4f4f4;">
                <td style="padding: 8px; font-weight: bold;">Area</td>
                <td style="padding: 8px;">{area_str}</td>
            </tr>
            <tr>
                <td style="padding: 8px; font-weight: bold;">Type</td>
                <td style="padding: 8px;">{modes_str}</td>
            </tr>
            <tr style="background: #f4f4f4;">
                <td style="padding: 8px; font-weight: bold;">Equipment</td>
                <td style="padding: 8px;">{equip_str}</td>
            </tr>
        </table>
        <br>
        <a href="{listing_url}"
           style="background: #e63946; color: white; padding: 12px 24px;
                  text-decoration: none; border-radius: 5px; font-weight: bold;
                  display: inline-block;">
            View listing
        </a>
        <p style="color: #999; font-size: 12px; margin-top: 20px;">
            Sent by your CROUS scraper bot.
        </p>
    </body>
    </html>
    """


def _build_message(item: dict, recipients: list) -> EmailMessage:
    residence = item.get("residence", {})
    name = item.get("label", residence.get("label", "Unknown listing"))
    listing_url = item.get("url", "https://trouverunlogement.lescrous.fr/")

    msg = EmailMessage()
    msg["From"] = f"{SENDER_NAME} <{SENDER_EMAIL}>"
    msg["To"] = ", ".join(recipients)
    msg["Subject"] = f"CROUS room available: {name}"
    msg.set_content(
        "A CROUS room is now available.\n"
        f"Listing: {name}\n"
        f"Link: {listing_url}\n"
    )
    msg.add_alternative(build_html(item), subtype="html")
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
        logging.warning(
            "Unknown SMTP_SECURITY='%s'. Falling back to starttls.",
            security,
        )
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


def send_alert(item: dict) -> bool:
    recipients = load_recipients()
    if not recipients:
        logging.error("No recipients configured. Set RECIPIENT_EMAIL in .env.")
        return False
    if _missing_smtp_config():
        return False

    msg = _build_message(item, recipients)
    residence = item.get("residence", {})
    name = item.get("label", residence.get("label", "Unknown listing"))

    try:
        with _open_smtp() as client:
            client.login(SMTP_USERNAME, SMTP_PASSWORD)
            client.send_message(msg)
        logging.info("Email sent for listing: %s -> %s", name, ", ".join(recipients))
        return True
    except Exception as e:
        logging.error("Unexpected SMTP error while sending email: %s", e)
        return False
