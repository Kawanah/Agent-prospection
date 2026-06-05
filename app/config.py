"""
Configuration de l'application.
Charge les variables d'environnement depuis .env
"""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Configuration de l'application chargée depuis les variables d'environnement."""

    # Application
    app_name: str = "Agent Prospection Kawanah Tourisme"
    app_env: str = "development"
    debug: bool = False

    # Database
    database_url: str = "sqlite+aiosqlite:///./data/prospection.db"

    # AI - Claude
    anthropic_api_key: str = ""

    # Enrichissement
    hunter_api_key: str = ""
    dropcontact_api_key: str = ""
    pappers_api_key: str = (
        ""  # Pappers.fr — données légales françaises (dirigeants, SIREN)
    )

    # DataForSEO (analyse SEO réelle — mots-clés positionnés, trafic organique)
    dataforseo_login: str = ""
    dataforseo_password: str = ""

    # Google Places API (avis Google + source de leads)
    google_places_api_key: str = ""

    # DATAtourisme (source de leads : gîtes, chambres d'hôtes, activités)
    # Inscription gratuite : https://www.datatourisme.fr/obtenir-et-utiliser-la-donnee/
    datatourisme_api_key: str = ""

    # Email
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    email_from: str = ""

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # LinkedIn (optionnel)
    linkedin_email: str = ""
    linkedin_password: str = ""

    # CORS — origines autorisées en production (séparées par des virgules)
    allowed_origins: str = ""

    # Garde-fous d'administration
    enable_runtime_settings: bool = False
    enable_admin_purge: bool = False
    enable_email_delivery: bool = False
    enable_auto_queue: bool = False

    # Prise de rendez-vous
    booking_link: str = "https://app.lemcal.com/@kawanah/presentation"

    # Authentication JWT
    secret_key: str = "change-me-in-production-use-openssl-rand-hex-32"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440  # 24h
    admin_username: str = "admin"
    admin_password_hash: str = ""  # Généré via: python -c "from passlib.context import CryptContext; print(CryptContext(schemes=['bcrypt']).hash('votre-mdp'))"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    """Retourne l'instance de configuration (mise en cache)."""
    return Settings()
