"""
Point d'entrée de l'API FastAPI - Agent de Prospection Kawanah Travel.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.config import get_settings
from app.database import init_db

limiter = Limiter(key_func=get_remote_address)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestion du cycle de vie de l'application."""
    # Startup
    logger.info(f"Démarrage de {settings.app_name}...")
    await init_db()
    logger.info("Base de données initialisée.")
    yield
    # Shutdown
    logger.info("Arrêt de l'application...")


app = FastAPI(
    title=settings.app_name,
    description="Agent de prospection automatisé pour le secteur hospitalité - Kawanah Travel",
    version="0.1.0",
    lifespan=lifespan,
)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Configuration CORS
ALLOWED_ORIGINS = [
    "http://localhost:5173",  # Vite dev
    "http://localhost:5174",  # Vite dev (port alternatif)
    "http://localhost:5175",  # Vite dev (port alternatif)
    "http://localhost:4173",  # Vite preview
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5174",
    "http://127.0.0.1:5175",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Route racine - Vérification que l'API fonctionne."""
    return {
        "message": f"Bienvenue sur {settings.app_name}",
        "version": "0.1.0",
        "status": "running",
    }


@app.get("/health")
async def health_check():
    """Vérification de santé de l'application."""
    return {"status": "healthy"}


# Routers API
from fastapi import Depends
from app.auth import get_current_user
from app.api import (
    leads,
    contacts,
    campaigns,
    messages,
    enrichment,
    scoring,
    ai_messages,
    agent,
    reviews,
    gouv_data,
)
from app.api import settings as settings_api
from app.api import auth as auth_api

# Route publique : login (pas de protection JWT)
app.include_router(auth_api.router, prefix="/api/auth", tags=["Authentification"])

# Toutes les autres routes sont protégées par JWT
_auth = [Depends(get_current_user)]

app.include_router(
    leads.router, prefix="/api/leads", tags=["Leads"], dependencies=_auth
)
app.include_router(
    contacts.router, prefix="/api/contacts", tags=["Contacts"], dependencies=_auth
)
app.include_router(
    campaigns.router, prefix="/api/campaigns", tags=["Campaigns"], dependencies=_auth
)
app.include_router(
    messages.router, prefix="/api/messages", tags=["Messages"], dependencies=_auth
)
app.include_router(
    enrichment.router,
    prefix="/api/enrichment",
    tags=["Enrichissement"],
    dependencies=_auth,
)
app.include_router(
    scoring.router,
    prefix="/api/scoring",
    tags=["Scoring & Priorisation"],
    dependencies=_auth,
)
app.include_router(
    ai_messages.router, prefix="/api/ai", tags=["Génération IA"], dependencies=_auth
)
app.include_router(
    agent.router, prefix="/api/agent", tags=["Agent Autonome"], dependencies=_auth
)
app.include_router(
    reviews.router, prefix="/api/reviews", tags=["Avis Google"], dependencies=_auth
)
app.include_router(
    settings_api.router, prefix="/api/settings", tags=["Paramètres"], dependencies=_auth
)
app.include_router(
    gouv_data.router,
    prefix="/api/gouv",
    tags=["Import data.gouv.fr"],
    dependencies=_auth,
)
