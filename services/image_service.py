import logging
import uuid
from datetime import datetime
from typing import Dict, Any, Optional
import httpx
import boto3
from botocore.exceptions import ClientError

from core.config import settings
from .intervention_service import add_image_reference, get_image_references

logger = logging.getLogger(__name__)


def get_s3_client():
    """Retourne un client S3."""
    if not settings.s3_bucket_name:
        logger.warning("S3 bucket name not configured")
        return None

    return boto3.client("s3", region_name=settings.aws_region_name)


def generate_s3_key(phone: str, reference: str, extension: str = "jpg") -> str:
    """
    Genere une cle S3 unique pour une image.

    Format: {phone}/{reference}/{timestamp}_{uuid}.{ext}
    """
    # Nettoyer le numero de telephone
    clean_phone = phone.replace("whatsapp:", "").replace("+", "")
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    unique_id = str(uuid.uuid4())[:8]

    return f"{clean_phone}/{reference}/{timestamp}_{unique_id}.{extension}"


async def download_image_from_twilio(media_url: str) -> Optional[bytes]:
    """
    Telecharge une image depuis l'URL Twilio.

    Args:
        media_url: URL de l'image Twilio

    Returns:
        Bytes de l'image ou None si erreur
    """
    if not settings.twilio_account_sid or not settings.twilio_auth_token:
        logger.warning("Twilio credentials not configured")
        return None

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                media_url,
                auth=(settings.twilio_account_sid, settings.twilio_auth_token),
                follow_redirects=True,
                timeout=30.0
            )
            response.raise_for_status()
            return response.content
    except Exception as e:
        logger.error(f"Error downloading image from Twilio: {e}")
        return None


def download_image_from_twilio_sync(media_url: str) -> Optional[bytes]:
    """
    Telecharge une image depuis l'URL Twilio (version synchrone).

    Args:
        media_url: URL de l'image Twilio

    Returns:
        Bytes de l'image ou None si erreur
    """
    if not settings.twilio_account_sid or not settings.twilio_auth_token:
        logger.warning("Twilio credentials not configured")
        return None

    try:
        with httpx.Client() as client:
            response = client.get(
                media_url,
                auth=(settings.twilio_account_sid, settings.twilio_auth_token),
                follow_redirects=True,
                timeout=30.0
            )
            response.raise_for_status()
            return response.content
    except Exception as e:
        logger.error(f"Error downloading image from Twilio: {e}")
        return None


def upload_image_to_s3(
    image_data: bytes,
    s3_key: str,
    content_type: str = "image/jpeg"
) -> Dict[str, Any]:
    """
    Upload une image vers S3.

    Args:
        image_data: Bytes de l'image
        s3_key: Cle S3 de destination
        content_type: Type MIME de l'image

    Returns:
        Dict avec le resultat
    """
    s3_client = get_s3_client()
    if not s3_client:
        return {"error": "S3 non configure"}

    try:
        s3_client.put_object(
            Bucket=settings.s3_bucket_name,
            Key=s3_key,
            Body=image_data,
            ContentType=content_type
        )
        logger.info(f"Image uploaded to S3: {s3_key}")
        return {"success": True, "s3_key": s3_key}
    except ClientError as e:
        logger.error(f"S3 upload error: {e}")
        return {"error": f"Erreur upload S3: {str(e)}"}


def get_presigned_url(s3_key: str, expiration: int = 3600) -> Optional[str]:
    """
    Genere une URL presignee pour acceder a une image S3.

    Args:
        s3_key: Cle S3 de l'image
        expiration: Duree de validite en secondes (defaut: 1h)

    Returns:
        URL presignee ou None si erreur
    """
    s3_client = get_s3_client()
    if not s3_client:
        return None

    try:
        url = s3_client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": settings.s3_bucket_name,
                "Key": s3_key
            },
            ExpiresIn=expiration
        )
        return url
    except ClientError as e:
        logger.error(f"Error generating presigned URL: {e}")
        return None


def upload_image(
    phone: str,
    reference: str,
    media_url: str
) -> Dict[str, Any]:
    """
    Telecharge une image depuis Twilio et l'upload vers S3.
    Met a jour la reference dans DynamoDB.

    Args:
        phone: Numero WhatsApp du technicien
        reference: Reference de l'intervention
        media_url: URL de l'image Twilio

    Returns:
        Dict avec le resultat
    """
    # 1. Telecharger l'image depuis Twilio
    image_data = download_image_from_twilio_sync(media_url)
    if not image_data:
        return {"error": "Impossible de telecharger l'image"}

    # 2. Generer la cle S3
    # Detecter l'extension depuis le content-type si possible
    extension = "jpg"  # Default
    s3_key = generate_s3_key(phone, reference, extension)

    # 3. Upload vers S3
    upload_result = upload_image_to_s3(image_data, s3_key)
    if "error" in upload_result:
        return upload_result

    # 4. Mettre a jour DynamoDB
    db_result = add_image_reference(phone, reference, s3_key)
    if "error" in db_result:
        return db_result

    return {
        "success": True,
        "reference": reference,
        "s3_key": s3_key,
        "message": "Image ajoutee avec succes"
    }


def get_images(phone: str, reference: str) -> Dict[str, Any]:
    """
    Recupere les URLs presignees des images d'une intervention.

    Args:
        phone: Numero WhatsApp du technicien
        reference: Reference de l'intervention

    Returns:
        Dict avec les URLs des images
    """
    # 1. Recuperer les references depuis DynamoDB
    db_result = get_image_references(phone, reference)
    if "error" in db_result:
        return db_result

    images = db_result.get("images", [])
    if not images:
        return {
            "success": True,
            "reference": reference,
            "count": 0,
            "images": [],
            "message": "Aucune image pour cette intervention"
        }

    # 2. Generer les URLs presignees
    image_urls = []
    for img in images:
        s3_key = img.get("s3_key")
        if s3_key:
            url = get_presigned_url(s3_key)
            if url:
                image_urls.append({
                    "url": url,
                    "uploaded_at": img.get("uploaded_at")
                })

    return {
        "success": True,
        "reference": reference,
        "count": len(image_urls),
        "images": image_urls
    }
