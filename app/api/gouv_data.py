"""
Routes API — Import data.gouv.fr avec jobs et checkpoint.

Endpoints :
  POST   /api/gouv/jobs              → Créer un job (sans le lancer)
  POST   /api/gouv/jobs/{id}/start   → Lancer/reprendre un job
  POST   /api/gouv/jobs/{id}/pause   → Mettre en pause
  GET    /api/gouv/jobs              → Lister tous les jobs
  GET    /api/gouv/jobs/{id}         → Statut d'un job (pour polling)
  GET    /api/gouv/datasets/search   → Rechercher des datasets
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.gouv_data_service import GouvDataService, DATASET_SLUG

router = APIRouter()


# ─── Schémas ──────────────────────────────────────────────────────────────────


class CreateJobRequest(BaseModel):
    lead_types: list[str] = Field(
        default=["hotel", "camping", "gite", "chambre_hotes"],
        description="Types d'établissements à importer",
    )
    region: Optional[str] = Field(None, description="Ex: 'Bretagne', 'Normandie'")
    department: Optional[str] = Field(
        None, description="Code département ex: '06', '75'"
    )
    star_filter: Optional[list[str]] = Field(
        None, description="Filtrer par étoiles ex: ['1', '2', '3']. null = tous"
    )
    dataset_slug: str = Field(
        default=DATASET_SLUG, description="Slug du dataset data.gouv.fr"
    )
    batch_size: int = Field(default=100, ge=10, le=500)


# ─── Endpoints ────────────────────────────────────────────────────────────────


@router.post("/jobs", summary="Créer un job d'import")
async def create_job(
    body: CreateJobRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Crée un job d'import data.gouv.fr (statut PENDING).
    Le job n'est pas encore lancé — appeler /jobs/{id}/start ensuite.
    """
    if not body.region and not body.department:
        raise HTTPException(
            status_code=422,
            detail="Veuillez sélectionner au minimum un département ou une région. "
            "Travaillez département par département pour garder le contrôle.",
        )

    service = GouvDataService()
    try:
        job = await service.create_job(
            db=db,
            lead_types=body.lead_types,
            region=body.region,
            department=body.department,
            star_filter=body.star_filter,
            dataset_slug=body.dataset_slug,
            batch_size=body.batch_size,
        )
        return {
            "job_id": job.id,
            "status": job.status,
            "message": f"Job #{job.id} créé. Appeler POST /jobs/{job.id}/start pour le lancer.",
        }
    finally:
        await service.close()


@router.post("/jobs/{job_id}/start", summary="Lancer ou reprendre un job")
async def start_job(
    job_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Lance un job PENDING ou reprend un job PAUSED/FAILED depuis son checkpoint.
    L'import tourne en arrière-plan — utiliser GET /jobs/{id} pour suivre la progression.
    """
    service = GouvDataService()

    async def run():
        async for event in service.start_job(db, job_id):
            # Les événements sont loggés — le frontend poll GET /jobs/{id}
            pass
        await service.close()

    background_tasks.add_task(run)

    return {
        "job_id": job_id,
        "message": f"Job #{job_id} lancé en arrière-plan. Suivre avec GET /api/gouv/jobs/{job_id}",
    }


@router.post("/jobs/{job_id}/pause", summary="Mettre un job en pause")
async def pause_job(
    job_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Met un job en pause après le lot en cours."""
    service = GouvDataService()
    try:
        success = await service.pause_job(db, job_id)
        if not success:
            raise HTTPException(
                status_code=400, detail="Job introuvable ou non en cours d'exécution"
            )
        return {"job_id": job_id, "message": "Job mis en pause — reprendre avec /start"}
    finally:
        await service.close()


@router.get("/jobs", summary="Lister tous les jobs")
async def list_jobs(db: AsyncSession = Depends(get_db)):
    """Retourne tous les jobs d'import, du plus récent au plus ancien."""
    service = GouvDataService()
    try:
        jobs = await service.list_jobs(db)
        return {"jobs": jobs, "count": len(jobs)}
    finally:
        await service.close()


@router.get("/jobs/{job_id}", summary="Statut d'un job")
async def get_job(job_id: int, db: AsyncSession = Depends(get_db)):
    """
    Retourne l'état courant d'un job.
    À appeler en polling depuis le frontend pour suivre la progression.
    """
    service = GouvDataService()
    try:
        status = await service.get_job_status(db, job_id)
        if not status:
            raise HTTPException(status_code=404, detail=f"Job #{job_id} introuvable")
        return status
    finally:
        await service.close()


@router.get("/datasets/search", summary="Rechercher des datasets sur data.gouv.fr")
async def search_datasets(
    q: str = Query(
        default="hébergements touristiques hôtels", description="Termes de recherche"
    )
):
    """Recherche des datasets touristiques sur data.gouv.fr."""
    service = GouvDataService()
    try:
        results = await service.search_datasets(q)
        return {"datasets": results, "count": len(results)}
    finally:
        await service.close()
