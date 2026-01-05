import httpx
import logging
from typing import Dict, Any
from base64 import b64encode

from core.config import settings

logger = logging.getLogger(__name__)

TWILIO_API_URL = "https://api.twilio.com/2010-04-01"


def get_auth_header() -> str:
    """Génère le header d'authentification Basic pour Twilio."""
    credentials = f"{settings.twilio_account_sid}:{settings.twilio_auth_token}"
    encoded = b64encode(credentials.encode()).decode()
    return f"Basic {encoded}"


async def send_whatsapp_message(to: str, message: str) -> Dict[str, Any]:
    """
    Envoie un message WhatsApp via l'API Twilio.

    Args:
        to: Numéro du destinataire (format: whatsapp:+33612345678)
        message: Contenu du message à envoyer

    Returns:
        Dict contenant la réponse de l'API Twilio
    """
    if not settings.twilio_account_sid or not settings.twilio_auth_token:
        logger.error("Twilio credentials not configured")
        return {"success": False, "error": "Twilio credentials not configured"}

    # S'assurer que le numéro est au bon format
    if not to.startswith("whatsapp:"):
        to = f"whatsapp:{to}"

    url = f"{TWILIO_API_URL}/Accounts/{settings.twilio_account_sid}/Messages.json"

    data = {
        "From": settings.twilio_whatsapp_number,
        "To": to,
        "Body": message,
    }

    headers = {
        "Authorization": get_auth_header(),
        "Content-Type": "application/x-www-form-urlencoded",
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, data=data, headers=headers)

            if response.status_code in [200, 201]:
                logger.info(f"Message sent successfully to {to}")
                return {"success": True, "data": response.json()}
            else:
                logger.error(f"Failed to send message: {response.text}")
                return {"success": False, "error": response.text}

    except Exception as e:
        logger.error(f"Error sending WhatsApp message: {e}")
        return {"success": False, "error": str(e)}


async def send_whatsapp_media(
    to: str, media_url: str, caption: str = ""
) -> Dict[str, Any]:
    """
    Envoie un média (image, PDF) via WhatsApp.

    Args:
        to: Numéro du destinataire
        media_url: URL du média à envoyer
        caption: Légende optionnelle

    Returns:
        Dict contenant la réponse de l'API Twilio
    """
    if not settings.twilio_account_sid or not settings.twilio_auth_token:
        logger.error("Twilio credentials not configured")
        return {"success": False, "error": "Twilio credentials not configured"}

    if not to.startswith("whatsapp:"):
        to = f"whatsapp:{to}"

    url = f"{TWILIO_API_URL}/Accounts/{settings.twilio_account_sid}/Messages.json"

    data = {
        "From": settings.twilio_whatsapp_number,
        "To": to,
        "MediaUrl": media_url,
    }

    if caption:
        data["Body"] = caption

    headers = {
        "Authorization": get_auth_header(),
        "Content-Type": "application/x-www-form-urlencoded",
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, data=data, headers=headers)

            if response.status_code in [200, 201]:
                logger.info(f"Media sent successfully to {to}")
                return {"success": True, "data": response.json()}
            else:
                logger.error(f"Failed to send media: {response.text}")
                return {"success": False, "error": response.text}

    except Exception as e:
        logger.error(f"Error sending WhatsApp media: {e}")
        return {"success": False, "error": str(e)}


def parse_incoming_webhook(form_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parse les données d'un webhook Twilio entrant.

    Args:
        form_data: Données du formulaire envoyées par Twilio

    Returns:
        Dict avec les informations extraites du message
    """
    return {
        "from": form_data.get("From", ""),
        "to": form_data.get("To", ""),
        "body": form_data.get("Body", ""),
        "num_media": int(form_data.get("NumMedia", 0)),
        "media_urls": [
            form_data.get(f"MediaUrl{i}")
            for i in range(int(form_data.get("NumMedia", 0)))
            if form_data.get(f"MediaUrl{i}")
        ],
        "media_types": [
            form_data.get(f"MediaContentType{i}")
            for i in range(int(form_data.get("NumMedia", 0)))
            if form_data.get(f"MediaContentType{i}")
        ],
        "message_sid": form_data.get("MessageSid", ""),
        "account_sid": form_data.get("AccountSid", ""),
    }
