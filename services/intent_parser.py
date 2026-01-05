import re
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from models.actions import Action


@dataclass
class ParseResult:
    success: bool
    action: Optional[Action] = None
    data: Optional[Dict[str, Any]] = None
    ambiguous: bool = False


# Patterns pour les types d'intervention
INTERVENTION_TYPES = [
    "RAC IMMEUBLE",
    "RAC",
    "SAV",
    "RECO",
    "PRESTA",
    "RACCORDEMENT",
    "MAINTENANCE",
    "INSTALLATION",
]

# Pattern pour détecter une référence (numérique ou alphanumérique)
REFERENCE_PATTERN = r"\b([A-Za-z0-9]{6,15})\b"

# Pattern pour les dates (DD/MM/YYYY ou YYYY-MM-DD)
DATE_PATTERN = r"(\d{2}/\d{2}/\d{4}|\d{4}-\d{2}-\d{2})"


def normalize_text(text: str) -> str:
    """Normalise le texte pour faciliter la détection."""
    return text.strip().upper()


def extract_reference(text: str) -> Optional[str]:
    """Extrait une référence d'intervention du texte."""
    # Cherche d'abord un nombre long (type référence)
    numbers = re.findall(r"\b(\d{6,15})\b", text)
    if numbers:
        return numbers[0]

    # Sinon cherche un pattern alphanumérique
    alphanums = re.findall(r"\b([A-Z0-9]{6,15})\b", text.upper())
    if alphanums:
        return alphanums[0]

    return None


def extract_date(text: str) -> Optional[str]:
    """Extrait une date du texte."""
    # Format DD/MM/YYYY
    match = re.search(r"(\d{2})/(\d{2})/(\d{4})", text)
    if match:
        day, month, year = match.groups()
        return f"{year}-{month}-{day}"

    # Format YYYY-MM-DD
    match = re.search(r"(\d{4})-(\d{2})-(\d{2})", text)
    if match:
        return match.group(0)

    return None


def extract_intervention_type(text: str) -> Optional[str]:
    """Extrait le type d'intervention du texte."""
    text_upper = text.upper()

    # Vérifier les types connus
    for itype in INTERVENTION_TYPES:
        if itype in text_upper:
            return itype

    return None


def detect_help(text: str) -> bool:
    """Détecte une demande d'aide."""
    keywords = ["AIDE", "HELP", "AIDEZ", "AIDER", "COMMENT", "?"]
    text_upper = normalize_text(text)
    return any(kw in text_upper for kw in keywords) and len(text) < 50


def detect_delete(text: str) -> Optional[Dict[str, Any]]:
    """Détecte une demande de suppression."""
    keywords = ["SUPPRIMER", "ANNULER", "SUPPR", "DELETE", "EFFACER"]
    text_upper = normalize_text(text)

    if any(kw in text_upper for kw in keywords):
        ref = extract_reference(text)
        if ref:
            return {"reference": ref}
    return None


def detect_update(text: str) -> Optional[Dict[str, Any]]:
    """Détecte une demande de modification."""
    keywords = ["MODIFIER", "CORRIGER", "CHANGER", "UPDATE", "MODIF"]
    text_upper = normalize_text(text)

    if any(kw in text_upper for kw in keywords):
        ref = extract_reference(text)
        if ref:
            # Cherche le champ à modifier
            fields = {}

            # Cherche un nouveau type
            new_type = None
            type_match = re.search(r"TYPE\s+([A-Z\s]+)", text_upper)
            if type_match:
                potential_type = type_match.group(1).strip()
                for itype in INTERVENTION_TYPES:
                    if itype in potential_type:
                        new_type = itype
                        break
                if not new_type and potential_type:
                    new_type = potential_type.split()[0]

            if new_type:
                fields["type"] = new_type

            if fields:
                return {"reference": ref, "fields": fields}
            else:
                # Modification demandée mais champs non spécifiés
                return None
    return None


def detect_list(text: str) -> Optional[Dict[str, Any]]:
    """Détecte une demande de listing."""
    text_upper = normalize_text(text)

    if "AUJOURD'HUI" in text_upper or "AUJOURDHUI" in text_upper:
        return {"scope": "TODAY"}

    if "MOIS" in text_upper:
        return {"scope": "MOIS"}

    if "LISTE" in text_upper or "LISTER" in text_upper:
        date = extract_date(text)
        if date:
            return {"scope": "DATE", "date": date}
        return {"scope": "TODAY"}

    return None


def detect_search(text: str) -> Optional[Dict[str, Any]]:
    """Détecte une demande de recherche."""
    keywords = ["CHERCHER", "RECHERCHER", "VOIR", "DETAIL", "DÉTAIL", "TROUVER"]
    text_upper = normalize_text(text)

    if any(kw in text_upper for kw in keywords):
        ref = extract_reference(text)
        if ref:
            return {"reference": ref}
    return None


def detect_get_images(text: str) -> Optional[Dict[str, Any]]:
    """Détecte une demande d'affichage d'images."""
    keywords = ["IMAGES", "PHOTOS", "VOIR PHOTO", "VOIR IMAGE"]
    text_upper = normalize_text(text)

    if any(kw in text_upper for kw in keywords):
        ref = extract_reference(text)
        if ref:
            return {"reference": ref}
    return None


def detect_add_image(text: str, has_media: bool = False) -> Optional[Dict[str, Any]]:
    """Détecte l'ajout d'une image."""
    keywords = ["PHOTO", "IMAGE", "📸", "📷", "🖼"]
    text_upper = normalize_text(text)

    if has_media or any(kw in text_upper for kw in keywords):
        ref = extract_reference(text)
        if ref:
            return {"reference": ref}
        elif has_media:
            # Image reçue sans référence = erreur
            return None
    return None


def detect_add_comment(text: str) -> Optional[Dict[str, Any]]:
    """Détecte l'ajout d'un commentaire."""
    ref = extract_reference(text)
    if not ref:
        return None

    # Le texte après la référence ou après ":" est le commentaire
    # Pattern: référence : commentaire OU référence commentaire
    text_clean = text.strip()

    # Essaie de trouver le pattern "ref : commentaire"
    match = re.search(rf"{ref}\s*[:\-]\s*(.+)", text_clean, re.IGNORECASE)
    if match:
        comment = match.group(1).strip()
        if comment and len(comment) > 2:
            return {"reference": ref, "commentaire": comment}

    return None


def detect_create_bulk(text: str) -> Optional[Dict[str, Any]]:
    """Détecte la création multiple d'interventions."""
    lines = [l.strip() for l in text.strip().split("\n") if l.strip()]

    if len(lines) < 2:
        return None

    interventions = []
    date = extract_date(text) or "TODAY"

    for line in lines:
        itype = extract_intervention_type(line)
        ref = extract_reference(line)

        if itype and ref:
            interventions.append({"type": itype, "reference": ref})

    if len(interventions) >= 2:
        return {"date": date, "interventions": interventions}

    return None


def detect_create_one(text: str) -> Optional[Dict[str, Any]]:
    """Détecte la création d'une seule intervention."""
    itype = extract_intervention_type(text)
    ref = extract_reference(text)

    if itype and ref:
        date = extract_date(text) or "TODAY"
        return {"date": date, "type": itype, "reference": ref}

    return None


def parse_message(text: str, has_media: bool = False) -> ParseResult:
    """
    Parse un message et retourne l'intention détectée.

    Args:
        text: Le message texte du technicien
        has_media: True si le message contient une image/média

    Returns:
        ParseResult avec l'action détectée ou ambiguous=True si fallback OpenAI nécessaire
    """
    if not text or not text.strip():
        if has_media:
            # Image sans texte = erreur
            return ParseResult(
                success=True,
                action=Action.ERROR,
                data={"message": "Image reçue sans référence d'intervention"},
            )
        return ParseResult(
            success=True,
            action=Action.ERROR,
            data={"message": "Message vide"},
        )

    text = text.strip()

    # 1. HELP - Priorité haute
    if detect_help(text):
        return ParseResult(success=True, action=Action.HELP, data={})

    # 2. Image avec ou sans référence
    if has_media:
        result = detect_add_image(text, has_media=True)
        if result:
            return ParseResult(success=True, action=Action.ADD_IMAGE, data=result)
        else:
            return ParseResult(
                success=True,
                action=Action.ERROR,
                data={"message": "Image reçue sans référence d'intervention"},
            )

    # 3. DELETE
    result = detect_delete(text)
    if result:
        return ParseResult(success=True, action=Action.DELETE, data=result)

    # 4. UPDATE
    result = detect_update(text)
    if result:
        return ParseResult(success=True, action=Action.UPDATE, data=result)

    # 5. LIST
    result = detect_list(text)
    if result:
        return ParseResult(success=True, action=Action.LIST, data=result)

    # 6. SEARCH
    result = detect_search(text)
    if result:
        return ParseResult(success=True, action=Action.SEARCH, data=result)

    # 7. GET_IMAGES
    result = detect_get_images(text)
    if result:
        return ParseResult(success=True, action=Action.GET_IMAGES, data=result)

    # 8. ADD_IMAGE (mot-clé sans média)
    result = detect_add_image(text, has_media=False)
    if result:
        return ParseResult(success=True, action=Action.ADD_IMAGE, data=result)

    # 9. CREATE_BULK (plusieurs lignes avec type+ref)
    result = detect_create_bulk(text)
    if result:
        return ParseResult(success=True, action=Action.CREATE_BULK, data=result)

    # 10. CREATE_ONE (une ligne avec type+ref)
    result = detect_create_one(text)
    if result:
        return ParseResult(success=True, action=Action.CREATE_ONE, data=result)

    # 11. ADD_COMMENT (référence + texte libre)
    result = detect_add_comment(text)
    if result:
        return ParseResult(success=True, action=Action.ADD_COMMENT, data=result)

    # 12. Ambiguïté - fallback vers OpenAI
    return ParseResult(success=False, ambiguous=True)
