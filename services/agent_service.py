import json
import logging
from typing import Dict, Any, Optional
from openai import OpenAI

from core.config import settings
from core.prompts import AGENT_SYSTEM_PROMPT
from models.actions import Action
from .intent_parser import parse_message, ParseResult
from . import intervention_service
from . import image_service

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


def execute_action(
    phone: str,
    action: Action,
    data: Dict[str, Any],
    media_url: Optional[str] = None
) -> Dict[str, Any]:
    """
    Execute l'action parsee en appelant les services de base de donnees.

    Args:
        phone: Numero WhatsApp du technicien
        action: Action a executer
        data: Donnees associees a l'action
        media_url: URL de l'image Twilio (pour ADD_IMAGE)

    Returns:
        Dict avec le resultat de l'execution
    """
    try:
        if action == Action.CREATE_ONE:
            result = intervention_service.create_intervention(
                phone=phone,
                intervention_type=data.get("type", ""),
                reference=data.get("reference", ""),
                date=data.get("date")
            )
            if "error" in result:
                return {"action": Action.ERROR.value, "data": {"message": result["error"]}}
            return {"action": action.value, "data": result.get("intervention", data)}

        elif action == Action.CREATE_BULK:
            interventions = data.get("interventions", [])
            result = intervention_service.create_bulk_interventions(
                phone=phone,
                interventions=interventions,
                date=data.get("date")
            )
            if "error" in result:
                return {"action": Action.ERROR.value, "data": {"message": result["error"]}}
            return {
                "action": action.value,
                "data": {
                    "count": result.get("count", 0),
                    "interventions": result.get("created", [])
                }
            }

        elif action == Action.ADD_COMMENT:
            result = intervention_service.add_comment(
                phone=phone,
                reference=data.get("reference", ""),
                comment=data.get("comment", "")
            )
            if "error" in result:
                return {"action": Action.ERROR.value, "data": {"message": result["error"]}}
            return {"action": action.value, "data": data}

        elif action == Action.ADD_IMAGE:
            if not media_url:
                return {
                    "action": Action.ERROR.value,
                    "data": {"message": "Aucune image detectee dans le message"}
                }
            result = image_service.upload_image(
                phone=phone,
                reference=data.get("reference", ""),
                media_url=media_url
            )
            if "error" in result:
                return {"action": Action.ERROR.value, "data": {"message": result["error"]}}
            return {"action": action.value, "data": {"reference": data.get("reference")}}

        elif action == Action.UPDATE:
            fields = {}
            if "new_type" in data:
                fields["type"] = data["new_type"]
            if "new_date" in data:
                fields["date"] = data["new_date"]

            result = intervention_service.update_intervention(
                phone=phone,
                reference=data.get("reference", ""),
                fields=fields
            )
            if "error" in result:
                return {"action": Action.ERROR.value, "data": {"message": result["error"]}}
            return {"action": action.value, "data": data}

        elif action == Action.DELETE:
            result = intervention_service.delete_intervention(
                phone=phone,
                reference=data.get("reference", "")
            )
            if "error" in result:
                return {"action": Action.ERROR.value, "data": {"message": result["error"]}}
            return {"action": action.value, "data": {"reference": data.get("reference")}}

        elif action == Action.LIST:
            result = intervention_service.list_interventions(
                phone=phone,
                scope=data.get("scope", "today"),
                date=data.get("date")
            )
            if "error" in result:
                return {"action": Action.ERROR.value, "data": {"message": result["error"]}}
            return {
                "action": action.value,
                "data": {
                    "scope": result.get("scope"),
                    "count": result.get("count", 0),
                    "interventions": result.get("interventions", [])
                }
            }

        elif action == Action.SEARCH:
            result = intervention_service.get_intervention(
                phone=phone,
                reference=data.get("reference", "")
            )
            if "error" in result:
                return {"action": Action.ERROR.value, "data": {"message": result["error"]}}
            return {"action": action.value, "data": result.get("intervention", {})}

        elif action == Action.GET_IMAGES:
            result = image_service.get_images(
                phone=phone,
                reference=data.get("reference", "")
            )
            if "error" in result:
                return {"action": Action.ERROR.value, "data": {"message": result["error"]}}
            return {
                "action": action.value,
                "data": {
                    "reference": data.get("reference"),
                    "count": result.get("count", 0),
                    "images": result.get("images", [])
                }
            }

        elif action == Action.HELP:
            return {"action": action.value, "data": data}

        elif action == Action.ERROR:
            return {"action": action.value, "data": data}

        else:
            return {
                "action": Action.ERROR.value,
                "data": {"message": f"Action non supportee: {action.value}"}
            }

    except Exception as e:
        logger.error(f"Error executing action {action}: {e}")
        return {
            "action": Action.ERROR.value,
            "data": {"message": f"Erreur d'execution: {str(e)}"}
        }


def process_message(
    phone: str,
    message: str,
    has_media: bool = False,
    media_url: Optional[str] = None
) -> Dict[str, Any]:
    """
    Traite un message de technicien et retourne une réponse JSON.

    Approche hybride:
    1. Essaie d'abord le parser basé sur les règles Python
    2. Si ambigu, utilise OpenAI comme fallback
    3. Execute l'action en base de donnees

    Args:
        phone: Numéro WhatsApp du technicien
        message: Contenu du message
        has_media: True si le message contient une image/média
        media_url: URL de l'image Twilio (si presente)

    Returns:
        Dict avec structure {"action": "...", "data": {...}}
    """
    logger.info(f"Processing message from {phone}: {message[:50]}...")

    # Étape 1: Parser basé sur les règles
    parse_result: ParseResult = parse_message(message, has_media=has_media)

    parsed_response = None

    if parse_result.success and not parse_result.ambiguous:
        # Parsing réussi avec les règles Python
        logger.info(f"Rule-based parsing succeeded: {parse_result.action}")
        parsed_response = {
            "action": parse_result.action,
            "data": parse_result.data or {},
        }

    # Étape 2: Fallback vers OpenAI
    elif parse_result.ambiguous:
        logger.info("Message ambiguous, falling back to OpenAI")
        openai_result = call_openai_fallback(message, phone)
        try:
            action_str = openai_result.get("action", "ERROR")
            parsed_response = {
                "action": Action(action_str),
                "data": openai_result.get("data", {}),
            }
        except ValueError:
            return {
                "action": Action.ERROR.value,
                "data": {"message": "Action non reconnue"},
            }
    else:
        # Cas par défaut: erreur
        return {
            "action": Action.ERROR.value,
            "data": {"message": "Message non reconnu"},
        }

    # Étape 3: Executer l'action en base de donnees
    return execute_action(
        phone=phone,
        action=parsed_response["action"],
        data=parsed_response["data"],
        media_url=media_url
    )


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
        count = data.get("count", 0)
        scope = data.get("scope", "today")
        if count == 0:
            return f"📋 Aucune intervention ({scope})"

        lines = [f"📋 *{count} intervention(s)* ({scope}):"]
        for i, interv in enumerate(data.get("interventions", [])[:10], 1):
            lines.append(f"{i}. {interv.get('type', '')} - {interv.get('reference', '')}")
        if count > 10:
            lines.append(f"... et {count - 10} autres")
        return "\n".join(lines)

    elif action == Action.SEARCH.value:
        if not data.get("reference"):
            return "🔍 Intervention non trouvee"
        lines = [f"🔍 *Intervention {data.get('reference')}*"]
        lines.append(f"Type: {data.get('type', 'N/A')}")
        lines.append(f"Date: {data.get('date', 'N/A')}")
        comments_count = len(data.get("comments", []))
        images_count = data.get("images_count", 0)
        if comments_count > 0:
            lines.append(f"Commentaires: {comments_count}")
        if images_count > 0:
            lines.append(f"Images: {images_count}")
        return "\n".join(lines)

    elif action == Action.GET_IMAGES.value:
        count = data.get("count", 0)
        if count == 0:
            return f"🖼️ Aucune image pour {data.get('reference')}"
        lines = [f"🖼️ *{count} image(s)* pour {data.get('reference')}:"]
        for i, img in enumerate(data.get("images", [])[:5], 1):
            lines.append(f"{i}. {img.get('url', '')[:50]}...")
        return "\n".join(lines)

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
