import json
import logging
from fastapi import APIRouter, Request, Form, Response
from typing import Optional

from services.agent_service import process_message, format_response_for_whatsapp
from services.whatsapp_service import parse_incoming_webhook, send_whatsapp_message

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/whatsapp", tags=["WhatsApp"])


@router.post("/webhook")
async def receive_webhook(
    request: Request,
    From: str = Form(...),
    Body: str = Form(""),
    NumMedia: int = Form(0),
    MediaUrl0: Optional[str] = Form(None),
    MediaContentType0: Optional[str] = Form(None),
    MessageSid: str = Form(""),
):
    """
    Webhook pour recevoir les messages WhatsApp de Twilio.

    Twilio envoie les messages entrants via POST avec form-data.
    """
    logger.info(f"Received webhook from {From}: {Body[:50] if Body else '[media]'}...")

    # Extraire le numéro de téléphone (format: whatsapp:+33612345678)
    phone = From.replace("whatsapp:", "") if From.startswith("whatsapp:") else From

    # Détecter si le message contient des médias
    has_media = NumMedia > 0

    # Traiter le message avec l'agent
    response = process_message(phone=phone, message=Body, has_media=has_media)

    logger.info(f"Agent response: {response}")

    # Formater la réponse pour WhatsApp (message lisible)
    whatsapp_message = format_response_for_whatsapp(response)

    # Envoyer la réponse au technicien
    await send_whatsapp_message(to=From, message=whatsapp_message)

    # Retourner une réponse TwiML vide pour confirmer la réception
    # Twilio attend une réponse XML valide
    twiml_response = '<?xml version="1.0" encoding="UTF-8"?><Response></Response>'

    return Response(content=twiml_response, media_type="application/xml")


@router.post("/process")
async def process_direct(
    message: str,
    phone: str,
    has_media: bool = False,
):
    """
    Endpoint direct pour traiter un message sans passer par Twilio.

    Utile pour les tests et l'intégration avec d'autres systèmes.
    """
    response = process_message(phone=phone, message=message, has_media=has_media)
    return response


@router.get("/health")
async def health_check():
    """Endpoint de vérification de santé."""
    return {"status": "ok", "service": "Agent Lynkia"}
