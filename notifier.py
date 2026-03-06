"""
Sends email notifications via brevo-python v4 SDK (imported as 'brevo').
"""
import logging
from brevo import Brevo
from brevo.core.api_error import ApiError
from brevo.transactional_emails import (
    SendTransacEmailRequestSender,
    SendTransacEmailRequestToItem,
)
from config import BREVO_API_KEY, SENDER_EMAIL, SENDER_NAME, load_recipients


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
    for m in occupation_modes:
        mode_types.append(m.get("type", ""))
        r = m.get("rent", {})
        if r.get("min"):
            rents.append(r["min"] / 100)
        if r.get("max"):
            rents.append(r["max"] / 100)
    rent_str = f"{min(rents):.0f}–{max(rents):.0f} €/month" if rents else "N/A"
    modes_str = ", ".join(mode_types) if mode_types else "N/A"

    # Equipment
    equipments = item.get("equipments", [])
    equip_str = ", ".join(e.get("label", "") for e in equipments) if equipments else "N/A"

    # Area
    area = item.get("area", {})
    area_str = f"{area.get('min', '?')}–{area.get('max', '?')} m²"

    return f"""
    <html>
    <body style="font-family: Arial, sans-serif; padding: 20px; color: #333; max-width: 600px;">
        <h2 style="color: #e63946;">🏠 CROUS room just dropped!</h2>
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
            View listing →
        </a>
        <p style="color: #999; font-size: 12px; margin-top: 20px;">
            Sent by your CROUS scraper bot — go get it! 🎯
        </p>
    </body>
    </html>
    """


def send_alert(item: dict):
    if not BREVO_API_KEY:
        logging.error("BREVO_API_KEY is not set. Cannot send email.")
        return

    recipients = load_recipients()
    if not recipients:
        logging.error("No recipients configured. Add emails to recipients.txt or set RECIPIENT_EMAIL in .env")
        return

    residence = item.get("residence", {})
    name = item.get("label", residence.get("label", "Unknown listing"))

    try:
        client = Brevo(api_key=BREVO_API_KEY)
        client.transactional_emails.send_transac_email(
            sender=SendTransacEmailRequestSender(
                email=SENDER_EMAIL,
                name=SENDER_NAME,
            ),
            to=[
                SendTransacEmailRequestToItem(email=email, name=email.split("@")[0])
                for email in recipients
            ],
            subject=f"🏠 CROUS room available: {name}",
            html_content=build_html(item),
        )
        logging.info(f"Email sent for listing: {name} → {', '.join(recipients)}")

    except ApiError as e:
        logging.error(f"Brevo API error {e.status_code}: {e.body}")
    except Exception as e:
        logging.error(f"Unexpected error sending email: {e}")
