import json
import logging
from typing import Dict, Any, Optional
from openai import OpenAI

from core.config import settings
from core.prompts import AGENT_SYSTEM_PROMPT
from models.actions import Action
from .intent_parser import parse_message, ParseResult

logger = logging.getLogger(__name__)


def get_openai_client() -> Optional[OpenAI]:
    """Retourne un client OpenAI si configuré."""
    if settings.openai_api_key:
        return OpenAI(api_key=settings.openai_api_key)
    return None


def call_openai_fallback(message: str, phone: str) -> Dict[str, Any]:
    """
    Appelle OpenAI pour parser un message ambigu.

    Args:
        message: Le message du technicien
        phone: Le numéro WhatsApp du technicien

    Returns:
        Dict contenant l'action et les données parsées
    """
    client = get_openai_client()

    if not client:
        logger.warning("OpenAI API key not configured, returning error")
        return {
            "action": Action.ERROR.value,
            "data": {"message": "Service IA non disponible. Reformulez votre message."},
        }

    try:
        user_message = f"[Technicien: {phone}]\n{message}"

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": AGENT_SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            temperature=0,
            max_tokens=500,
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content
        result = json.loads(content)

        # Valider la structure
        if "action" not in result:
            result = {
                "action": Action.ERROR.value,
                "data": {"message": "Réponse IA invalide"},
            }

        return result

    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error from OpenAI: {e}")
        return {
            "action": Action.ERROR.value,
            "data": {"message": "Erreur de parsing de la réponse IA"},
        }
    except Exception as e:
        logger.error(f"OpenAI API error: {e}")
        return {
            "action": Action.ERROR.value,
            "data": {"message": f"Erreur du service IA: {str(e)}"},
        }


def process_message(
    phone: str, message: str, has_media: bool = False
) -> Dict[str, Any]:
    """
    Traite un message de technicien et retourne une réponse JSON.

    Approche hybride:
    1. Essaie d'abord le parser basé sur les règles Python
    2. Si ambigu, utilise OpenAI comme fallback

    Args:
        phone: Numéro WhatsApp du technicien
        message: Contenu du message
        has_media: True si le message contient une image/média

    Returns:
        Dict avec structure {"action": "...", "data": {...}}
    """
    logger.info(f"Processing message from {phone}: {message[:50]}...")

    # Étape 1: Parser basé sur les règles
    parse_result: ParseResult = parse_message(message, has_media=has_media)

    if parse_result.success and not parse_result.ambiguous:
        # Parsing réussi avec les règles Python
        logger.info(f"Rule-based parsing succeeded: {parse_result.action}")
        return {
            "action": parse_result.action.value,
            "data": parse_result.data or {},
        }

    # Étape 2: Fallback vers OpenAI
    if parse_result.ambiguous:
        logger.info("Message ambiguous, falling back to OpenAI")
        return call_openai_fallback(message, phone)

    # Cas par défaut: erreur
    return {
        "action": Action.ERROR.value,
        "data": {"message": "Message non reconnu"},
    }


def format_response_for_whatsapp(response: Dict[str, Any]) -> str:
    """
    Formate la réponse JSON pour envoi WhatsApp (optionnel).

    Pour debug ou confirmation, on peut envoyer un résumé lisible.
    """
    action = response.get("action", "UNKNOWN")
    data = response.get("data", {})

    if action == Action.CREATE_ONE.value:
        return f"✅ Intervention créée: {data.get('type')} - {data.get('reference')}"

    elif action == Action.CREATE_BULK.value:
        count = len(data.get("interventions", []))
        return f"✅ {count} interventions créées"

    elif action == Action.ADD_COMMENT.value:
        return f"💬 Commentaire ajouté sur {data.get('reference')}"

    elif action == Action.ADD_IMAGE.value:
        return f"📸 Image ajoutée sur {data.get('reference')}"

    elif action == Action.DELETE.value:
        return f"🗑️ Intervention {data.get('reference')} supprimée"

    elif action == Action.UPDATE.value:
        return f"✏️ Intervention {data.get('reference')} modifiée"

    elif action == Action.LIST.value:
        return f"📋 Liste des interventions ({data.get('scope')})"

    elif action == Action.SEARCH.value:
        return f"🔍 Recherche: {data.get('reference')}"

    elif action == Action.GET_IMAGES.value:
        return f"🖼️ Images de {data.get('reference')}"

    elif action == Action.HELP.value:
        return """📖 *Aide Agent Lynkia*

*Créer une intervention:*
RAC IMMEUBLE 149041830

*Créer plusieurs:*
RAC 123456
SAV 789012

*Ajouter un commentaire:*
149041830 : client absent

*Ajouter une photo:*
149041830 photo + envoyer image

*Modifier:*
MODIFIER 149041830 TYPE SAV

*Supprimer:*
SUPPRIMER 149041830

*Lister:*
LISTE AUJOURD'HUI
LISTE MOIS

*Rechercher:*
CHERCHER 149041830

*Voir images:*
IMAGES 149041830"""

    elif action == Action.ERROR.value:
        return f"❌ {data.get('message', 'Erreur inconnue')}"

    return json.dumps(response, ensure_ascii=False)
