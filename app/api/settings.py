"""
API endpoints pour la configuration de l'application.
Lit et écrit le fichier .env.
"""

from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.config import get_settings
from app.services.email_service import EmailService

router = APIRouter()

ENV_PATH = Path(".env")


def mask_key(value: str) -> str:
    """Masque une clé API : affiche les 6 premiers et 4 derniers caractères."""
    if not value or len(value) < 12:
        return value
    return f"{value[:6]}...{value[-4:]}"


def read_env_file() -> dict:
    """Lit le fichier .env et retourne un dict clé→valeur."""
    if not ENV_PATH.exists():
        return {}
    result = {}
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, val = line.partition("=")
            result[key.strip()] = val.strip()
    return result


def write_env_file(data: dict):
    """Réécrit le fichier .env en préservant les commentaires."""
    if not ENV_PATH.exists():
        lines = []
    else:
        lines = ENV_PATH.read_text(encoding="utf-8").splitlines()

    updated_keys = set()
    new_lines = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#") or not stripped or "=" not in stripped:
            new_lines.append(line)
            continue
        key, _, _ = stripped.partition("=")
        key = key.strip()
        if key in data:
            new_lines.append(f"{key}={data[key]}")
            updated_keys.add(key)
        else:
            new_lines.append(line)

    # Ajouter les nouvelles clés qui n'existaient pas dans le fichier
    for key, val in data.items():
        if key not in updated_keys:
            new_lines.append(f"{key}={val}")

    ENV_PATH.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


class SettingsResponse(BaseModel):
    """Paramètres retournés à l'interface (clés API masquées)."""

    # IA
    anthropic_api_key_masked: str
    anthropic_configured: bool
    # Enrichissement
    hunter_api_key_masked: str
    hunter_configured: bool
    google_places_api_key_masked: str
    google_configured: bool
    # Email
    smtp_host: str
    smtp_port: int
    smtp_user: str
    email_from: str
    smtp_configured: bool
    # LinkedIn
    linkedin_email: str


class SettingsSaveRequest(BaseModel):
    """Données envoyées depuis l'interface pour sauvegarder."""

    # IA (vide = ne pas modifier)
    anthropic_api_key: Optional[str] = None
    # Enrichissement
    hunter_api_key: Optional[str] = None
    google_places_api_key: Optional[str] = None
    # Email
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = None
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None
    email_from: Optional[str] = None
    # LinkedIn
    linkedin_email: Optional[str] = None
    linkedin_password: Optional[str] = None


@router.get("/", response_model=SettingsResponse)
async def get_settings_view():
    """Retourne la configuration actuelle (clés API masquées)."""
    env = read_env_file()

    anthropic = env.get("ANTHROPIC_API_KEY", "")
    hunter = env.get("HUNTER_API_KEY", "")
    google = env.get("GOOGLE_PLACES_API_KEY", "")

    return SettingsResponse(
        anthropic_api_key_masked=mask_key(anthropic),
        anthropic_configured=bool(anthropic and anthropic != "sk-ant-xxxxx"),
        hunter_api_key_masked=mask_key(hunter),
        hunter_configured=bool(hunter),
        google_places_api_key_masked=mask_key(google),
        google_configured=bool(google),
        smtp_host=env.get("SMTP_HOST", "smtp.gmail.com"),
        smtp_port=int(env.get("SMTP_PORT", "587")),
        smtp_user=env.get("SMTP_USER", ""),
        email_from=env.get("EMAIL_FROM", ""),
        smtp_configured=bool(env.get("SMTP_USER") and env.get("SMTP_PASSWORD")),
        linkedin_email=env.get("LINKEDIN_EMAIL", ""),
    )


@router.put("/")
async def save_settings(data: SettingsSaveRequest):
    """Sauvegarde les paramètres dans le fichier .env."""
    env = read_env_file()
    updates = {}

    # Ne mettre à jour que les champs non vides envoyés
    if data.anthropic_api_key:
        updates["ANTHROPIC_API_KEY"] = data.anthropic_api_key
    if data.hunter_api_key is not None:
        updates["HUNTER_API_KEY"] = data.hunter_api_key
    if data.google_places_api_key is not None:
        updates["GOOGLE_PLACES_API_KEY"] = data.google_places_api_key
    if data.smtp_host:
        updates["SMTP_HOST"] = data.smtp_host
    if data.smtp_port:
        updates["SMTP_PORT"] = str(data.smtp_port)
    if data.smtp_user is not None:
        updates["SMTP_USER"] = data.smtp_user
    if data.smtp_password:
        updates["SMTP_PASSWORD"] = data.smtp_password
    if data.email_from is not None:
        updates["EMAIL_FROM"] = data.email_from
    if data.linkedin_email is not None:
        updates["LINKEDIN_EMAIL"] = data.linkedin_email
    if data.linkedin_password:
        updates["LINKEDIN_PASSWORD"] = data.linkedin_password

    if not updates:
        raise HTTPException(status_code=400, detail="Aucune modification à sauvegarder")

    write_env_file(updates)

    # Invalider le cache config pour la prochaine requête
    get_settings.cache_clear()

    return {
        "success": True,
        "updated": list(updates.keys()),
        "message": "Paramètres sauvegardés dans .env",
    }


class TestEmailRequest(BaseModel):
    to_email: str


@router.post("/test-email")
async def send_test_email(data: TestEmailRequest):
    """
    Envoie un email de test pour vérifier la configuration SMTP.
    """
    get_settings.cache_clear()
    service = EmailService()

    if not service.is_configured():
        raise HTTPException(
            status_code=400,
            detail="Configuration SMTP incomplète. Renseignez host, port, user et mot de passe dans les paramètres.",
        )

    result = service.send_email(
        to_email=data.to_email,
        subject="✅ Test email — Agent Kawanah Tourisme",
        body=(
            "Bonjour,\n\n"
            "Cet email confirme que votre configuration SMTP fonctionne correctement.\n\n"
            "L'agent de prospection Kawanah Tourisme est prêt à envoyer des campagnes.\n\n"
            "— Agent Kawanah Tourisme"
        ),
    )

    if not result.success:
        raise HTTPException(status_code=500, detail=result.error)

    return {"success": True, "message": f"Email de test envoyé à {data.to_email}"}
