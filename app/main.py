"""
Point d'entrée de l'API FastAPI - Agent de Prospection Kawanah Tourisme.
"""

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.config import get_settings
from app.database import init_db, engine, Base, async_session
from app.models.import_batch import (
    ImportBatch,
)  # noqa: F401 — nécessaire pour create_all

limiter = Limiter(key_func=get_remote_address)

settings = get_settings()

# ─── Scheduler automatique de la file d'envoi ────────────────────────────────

QUEUE_INTERVAL_SECONDS = 5 * 60  # toutes les 5 minutes


async def _auto_process_queue():
    """
    Tâche de fond : traite la file d'envoi toutes les QUEUE_INTERVAL_SECONDS secondes.
    Lance les emails planifiés dont l'heure est venue, dans la limite du quota journalier.
    """
    from app.services.sequence_service import SequenceService

    service = SequenceService()

    while True:
        await asyncio.sleep(QUEUE_INTERVAL_SECONDS)
        try:
            async with async_session() as db:
                result = await service.process_queue(db)
                if result.get("sent", 0) > 0:
                    logger.info(f"[Auto-queue] {result['sent']} emails envoyés")
                elif result.get("quota_reached"):
                    logger.info(f"[Auto-queue] Quota journalier atteint")
        except Exception as e:
            logger.error(f"[Auto-queue] Erreur: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestion du cycle de vie de l'application."""
    # Startup
    logger.info(f"Démarrage de {settings.app_name}...")
    await init_db()
    logger.info("Base de données initialisée.")

    # Lancer le scheduler d'envoi en arrière-plan
    queue_task = asyncio.create_task(_auto_process_queue())
    logger.info(f"Scheduler d'envoi démarré (intervalle : {QUEUE_INTERVAL_SECONDS}s)")

    yield

    # Shutdown
    queue_task.cancel()
    logger.info("Arrêt de l'application...")


app = FastAPI(
    title=settings.app_name,
    description="Agent de prospection automatisé pour le secteur hospitalité - Kawanah Tourisme",
    version="0.1.0",
    lifespan=lifespan,
)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Configuration CORS
_DEV_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:5174",
    "http://localhost:5175",
    "http://localhost:5176",
    "http://localhost:5177",
    "http://localhost:5178",
    "http://localhost:5179",
    "http://localhost:5180",
    "http://localhost:4173",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5174",
    "http://127.0.0.1:5175",
    "http://127.0.0.1:5176",
    "http://127.0.0.1:5177",
    "http://127.0.0.1:5178",
    "http://127.0.0.1:5179",
    "http://127.0.0.1:5180",
]

_PROD_ORIGINS = [o.strip() for o in settings.allowed_origins.split(",") if o.strip()]

ALLOWED_ORIGINS = _PROD_ORIGINS if _PROD_ORIGINS else _DEV_ORIGINS

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception on {request.url}: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Une erreur interne est survenue"},
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
    sources,
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
app.include_router(
    sources.router,
    prefix="/api/sources",
    tags=["Nouvelles sources de leads"],
    dependencies=_auth,
)


@app.post("/api/admin/purge", tags=["Admin"], dependencies=_auth)
async def purge_all_data():
    """Vide toutes les tables sans supprimer la structure."""
    async with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(table.delete())
    logger.info("Toutes les données ont été purgées.")
    return {
        "message": "Toutes les données ont été effacées",
        "tables_purged": [t.name for t in Base.metadata.sorted_tables],
    }
