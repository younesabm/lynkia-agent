import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import boto3
from botocore.exceptions import ClientError

from core.config import settings

logger = logging.getLogger(__name__)


def get_dynamodb_table():
    """Retourne la table DynamoDB."""
    if not settings.dynamodb_table_name:
        logger.warning("DynamoDB table name not configured")
        return None

    dynamodb = boto3.resource("dynamodb", region_name=settings.aws_region_name)
    return dynamodb.Table(settings.dynamodb_table_name)


def create_intervention(
    phone: str,
    intervention_type: str,
    reference: str,
    date: Optional[str] = None
) -> Dict[str, Any]:
    """
    Crée une nouvelle intervention.

    Args:
        phone: Numéro WhatsApp du technicien
        intervention_type: Type d'intervention (RAC IMMEUBLE, SAV, etc.)
        reference: Référence unique
        date: Date de l'intervention (optionnel, défaut: aujourd'hui)

    Returns:
        Dict avec l'intervention créée ou erreur
    """
    table = get_dynamodb_table()
    if not table:
        return {"error": "Base de données non configurée"}

    now = datetime.utcnow().isoformat()
    intervention_date = date or datetime.utcnow().strftime("%Y-%m-%d")

    item = {
        "technicien_phone": phone,
        "reference": reference,
        "type": intervention_type.upper(),
        "date": intervention_date,
        "created_at": now,
        "updated_at": now,
        "status": "active",
        "comments": [],
        "images": []
    }

    try:
        # Vérifier si l'intervention existe déjà
        existing = table.get_item(
            Key={"technicien_phone": phone, "reference": reference}
        )
        if "Item" in existing and existing["Item"].get("status") == "active":
            return {"error": f"L'intervention {reference} existe déjà"}

        table.put_item(Item=item)
        logger.info(f"Intervention created: {reference} for {phone}")

        return {
            "success": True,
            "intervention": {
                "type": intervention_type.upper(),
                "reference": reference,
                "date": intervention_date
            }
        }
    except ClientError as e:
        logger.error(f"DynamoDB error: {e}")
        return {"error": f"Erreur base de données: {str(e)}"}


def create_bulk_interventions(
    phone: str,
    interventions: List[Dict[str, str]],
    date: Optional[str] = None
) -> Dict[str, Any]:
    """
    Crée plusieurs interventions en lot.

    Args:
        phone: Numéro WhatsApp du technicien
        interventions: Liste de {"type": "...", "reference": "..."}
        date: Date commune (optionnel)

    Returns:
        Dict avec le résultat
    """
    table = get_dynamodb_table()
    if not table:
        return {"error": "Base de données non configurée"}

    now = datetime.utcnow().isoformat()
    intervention_date = date or datetime.utcnow().strftime("%Y-%m-%d")

    created = []
    errors = []

    for intervention in interventions:
        ref = intervention.get("reference")
        int_type = intervention.get("type", "").upper()

        if not ref:
            continue

        item = {
            "technicien_phone": phone,
            "reference": ref,
            "type": int_type,
            "date": intervention_date,
            "created_at": now,
            "updated_at": now,
            "status": "active",
            "comments": [],
            "images": []
        }

        try:
            table.put_item(Item=item)
            created.append({"type": int_type, "reference": ref})
        except ClientError as e:
            errors.append({"reference": ref, "error": str(e)})

    return {
        "success": len(created) > 0,
        "created": created,
        "count": len(created),
        "errors": errors if errors else None
    }


def get_intervention(phone: str, reference: str) -> Dict[str, Any]:
    """
    Récupère une intervention par sa référence.

    Args:
        phone: Numéro WhatsApp du technicien
        reference: Référence de l'intervention

    Returns:
        Dict avec l'intervention ou erreur
    """
    table = get_dynamodb_table()
    if not table:
        return {"error": "Base de données non configurée"}

    try:
        response = table.get_item(
            Key={"technicien_phone": phone, "reference": reference}
        )

        if "Item" not in response:
            return {"error": f"Intervention {reference} non trouvée"}

        item = response["Item"]
        if item.get("status") == "deleted":
            return {"error": f"Intervention {reference} a été supprimée"}

        return {
            "success": True,
            "intervention": {
                "type": item.get("type"),
                "reference": item.get("reference"),
                "date": item.get("date"),
                "created_at": item.get("created_at"),
                "comments": item.get("comments", []),
                "images_count": len(item.get("images", []))
            }
        }
    except ClientError as e:
        logger.error(f"DynamoDB error: {e}")
        return {"error": f"Erreur base de données: {str(e)}"}


def list_interventions(
    phone: str,
    scope: str = "today",
    date: Optional[str] = None
) -> Dict[str, Any]:
    """
    Liste les interventions selon le scope.

    Args:
        phone: Numéro WhatsApp du technicien
        scope: "today", "week", "month", ou "all"
        date: Date spécifique (optionnel)

    Returns:
        Dict avec la liste des interventions
    """
    table = get_dynamodb_table()
    if not table:
        return {"error": "Base de données non configurée"}

    try:
        # Récupérer toutes les interventions du technicien
        response = table.query(
            KeyConditionExpression="technicien_phone = :phone",
            ExpressionAttributeValues={":phone": phone}
        )

        items = response.get("Items", [])

        # Filtrer par statut actif
        items = [i for i in items if i.get("status") == "active"]

        # Filtrer par date selon le scope
        today = datetime.utcnow().date()

        if scope == "today":
            target_date = today.isoformat()
            items = [i for i in items if i.get("date") == target_date]
        elif scope == "week":
            week_start = (today - timedelta(days=today.weekday())).isoformat()
            items = [i for i in items if i.get("date", "") >= week_start]
        elif scope == "month":
            month_start = today.replace(day=1).isoformat()
            items = [i for i in items if i.get("date", "") >= month_start]
        elif date:
            items = [i for i in items if i.get("date") == date]

        # Formater la réponse
        interventions = []
        for item in items:
            interventions.append({
                "type": item.get("type"),
                "reference": item.get("reference"),
                "date": item.get("date"),
                "comments_count": len(item.get("comments", [])),
                "images_count": len(item.get("images", []))
            })

        # Trier par date décroissante
        interventions.sort(key=lambda x: x.get("date", ""), reverse=True)

        return {
            "success": True,
            "scope": scope,
            "count": len(interventions),
            "interventions": interventions
        }
    except ClientError as e:
        logger.error(f"DynamoDB error: {e}")
        return {"error": f"Erreur base de données: {str(e)}"}


def update_intervention(
    phone: str,
    reference: str,
    fields: Dict[str, str]
) -> Dict[str, Any]:
    """
    Met à jour une intervention.

    Args:
        phone: Numéro WhatsApp du technicien
        reference: Référence de l'intervention
        fields: Champs à mettre à jour {"type": "...", "date": "..."}

    Returns:
        Dict avec le résultat
    """
    table = get_dynamodb_table()
    if not table:
        return {"error": "Base de données non configurée"}

    try:
        # Vérifier que l'intervention existe
        existing = table.get_item(
            Key={"technicien_phone": phone, "reference": reference}
        )
        if "Item" not in existing:
            return {"error": f"Intervention {reference} non trouvée"}

        if existing["Item"].get("status") == "deleted":
            return {"error": f"Intervention {reference} a été supprimée"}

        # Construire l'update expression
        update_parts = ["updated_at = :now"]
        expr_values = {":now": datetime.utcnow().isoformat()}

        if "type" in fields:
            update_parts.append("#t = :type")
            expr_values[":type"] = fields["type"].upper()

        if "date" in fields:
            update_parts.append("#d = :date")
            expr_values[":date"] = fields["date"]

        update_expr = "SET " + ", ".join(update_parts)
        expr_names = {"#t": "type", "#d": "date"}

        table.update_item(
            Key={"technicien_phone": phone, "reference": reference},
            UpdateExpression=update_expr,
            ExpressionAttributeValues=expr_values,
            ExpressionAttributeNames=expr_names
        )

        return {
            "success": True,
            "reference": reference,
            "updated_fields": list(fields.keys())
        }
    except ClientError as e:
        logger.error(f"DynamoDB error: {e}")
        return {"error": f"Erreur base de données: {str(e)}"}


def delete_intervention(phone: str, reference: str) -> Dict[str, Any]:
    """
    Supprime (soft delete) une intervention.

    Args:
        phone: Numéro WhatsApp du technicien
        reference: Référence de l'intervention

    Returns:
        Dict avec le résultat
    """
    table = get_dynamodb_table()
    if not table:
        return {"error": "Base de données non configurée"}

    try:
        # Vérifier que l'intervention existe
        existing = table.get_item(
            Key={"technicien_phone": phone, "reference": reference}
        )
        if "Item" not in existing:
            return {"error": f"Intervention {reference} non trouvée"}

        # Soft delete
        table.update_item(
            Key={"technicien_phone": phone, "reference": reference},
            UpdateExpression="SET #s = :status, updated_at = :now",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={
                ":status": "deleted",
                ":now": datetime.utcnow().isoformat()
            }
        )

        return {
            "success": True,
            "reference": reference,
            "deleted": True
        }
    except ClientError as e:
        logger.error(f"DynamoDB error: {e}")
        return {"error": f"Erreur base de données: {str(e)}"}


def add_comment(phone: str, reference: str, comment: str) -> Dict[str, Any]:
    """
    Ajoute un commentaire à une intervention.

    Args:
        phone: Numéro WhatsApp du technicien
        reference: Référence de l'intervention
        comment: Texte du commentaire

    Returns:
        Dict avec le résultat
    """
    table = get_dynamodb_table()
    if not table:
        return {"error": "Base de données non configurée"}

    try:
        # Vérifier que l'intervention existe
        existing = table.get_item(
            Key={"technicien_phone": phone, "reference": reference}
        )
        if "Item" not in existing:
            return {"error": f"Intervention {reference} non trouvée"}

        if existing["Item"].get("status") == "deleted":
            return {"error": f"Intervention {reference} a été supprimée"}

        now = datetime.utcnow().isoformat()
        comment_obj = {
            "text": comment,
            "created_at": now
        }

        table.update_item(
            Key={"technicien_phone": phone, "reference": reference},
            UpdateExpression="SET comments = list_append(if_not_exists(comments, :empty), :comment), updated_at = :now",
            ExpressionAttributeValues={
                ":comment": [comment_obj],
                ":empty": [],
                ":now": now
            }
        )

        return {
            "success": True,
            "reference": reference,
            "comment": comment
        }
    except ClientError as e:
        logger.error(f"DynamoDB error: {e}")
        return {"error": f"Erreur base de données: {str(e)}"}


def add_image_reference(phone: str, reference: str, s3_key: str) -> Dict[str, Any]:
    """
    Ajoute une référence d'image S3 à une intervention.

    Args:
        phone: Numéro WhatsApp du technicien
        reference: Référence de l'intervention
        s3_key: Clé S3 de l'image

    Returns:
        Dict avec le résultat
    """
    table = get_dynamodb_table()
    if not table:
        return {"error": "Base de données non configurée"}

    try:
        now = datetime.utcnow().isoformat()
        image_obj = {
            "s3_key": s3_key,
            "uploaded_at": now
        }

        table.update_item(
            Key={"technicien_phone": phone, "reference": reference},
            UpdateExpression="SET images = list_append(if_not_exists(images, :empty), :image), updated_at = :now",
            ExpressionAttributeValues={
                ":image": [image_obj],
                ":empty": [],
                ":now": now
            }
        )

        return {"success": True, "s3_key": s3_key}
    except ClientError as e:
        logger.error(f"DynamoDB error: {e}")
        return {"error": f"Erreur base de données: {str(e)}"}


def get_image_references(phone: str, reference: str) -> Dict[str, Any]:
    """
    Récupère les références d'images d'une intervention.

    Args:
        phone: Numéro WhatsApp du technicien
        reference: Référence de l'intervention

    Returns:
        Dict avec les clés S3 des images
    """
    table = get_dynamodb_table()
    if not table:
        return {"error": "Base de données non configurée"}

    try:
        response = table.get_item(
            Key={"technicien_phone": phone, "reference": reference}
        )

        if "Item" not in response:
            return {"error": f"Intervention {reference} non trouvée"}

        images = response["Item"].get("images", [])
        return {
            "success": True,
            "reference": reference,
            "images": images
        }
    except ClientError as e:
        logger.error(f"DynamoDB error: {e}")
        return {"error": f"Erreur base de données: {str(e)}"}
