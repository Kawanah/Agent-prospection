"""
API endpoints pour l'enrichissement des leads.
"""

import uuid
import asyncio
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from loguru import logger
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

from app.database import get_db, async_session as AsyncSessionLocal
from app.models.lead import Lead, LeadStatus
from app.services.enrichment_service import EnrichmentService

router = APIRouter()

# Stockage en mémoire des jobs d'enrichissement en cours
# { job_id: { status, total, current, results, error } }
_jobs: dict = {}


async def _run_enrichment_job(job_id: str, lead_ids: list[int], use_paid_apis: bool):
    """Tâche d'enrichissement en arrière-plan avec parallélisation contrôlée."""
    _jobs[job_id]["status"] = "running"
    semaphore = asyncio.Semaphore(3)  # Max 3 enrichissements simultanés

    async with AsyncSessionLocal() as db:
        service = EnrichmentService(db)

        async def _enrich_one(lead_id: int):
            async with semaphore:
                result_entry = await db.execute(select(Lead).where(Lead.id == lead_id))
                lead = result_entry.scalar_one_or_none()
                if not lead:
                    return
                try:
                    result = await service.enrich_lead(
                        lead, use_paid_apis=use_paid_apis
                    )
                    _jobs[job_id]["results"].append(result)
                except Exception as e:
                    _jobs[job_id]["results"].append(
                        {
                            "lead_id": lead_id,
                            "lead_name": getattr(lead, "name", f"Lead #{lead_id}"),
                            "error": str(e),
                        }
                    )
                _jobs[job_id]["current"] += 1
                await asyncio.sleep(
                    1
                )  # Pause entre requêtes pour éviter le rate limiting

        try:
            await asyncio.gather(*[_enrich_one(lid) for lid in lead_ids])
        finally:
            await service.close()

    _jobs[job_id]["status"] = "done"


# IMPORTANT: Les routes spécifiques AVANT les routes avec paramètres


@router.get("/stats")
async def get_enrichment_stats(db: AsyncSession = Depends(get_db)):
    """
    Retourne les statistiques d'enrichissement globales.
    """
    from sqlalchemy import func

    total_result = await db.execute(select(func.count(Lead.id)))
    total = total_result.scalar()

    enriched_result = await db.execute(
        select(func.count(Lead.id)).where(Lead.status == LeadStatus.ENRICHED)
    )
    enriched = enriched_result.scalar()

    with_email = await db.execute(
        select(func.count(Lead.id)).where(Lead.email.isnot(None))
    )

    with_phone = await db.execute(
        select(func.count(Lead.id)).where(Lead.phone.isnot(None))
    )

    with_social = await db.execute(
        select(func.count(Lead.id)).where(
            (Lead.facebook_url.isnot(None))
            | (Lead.instagram_url.isnot(None))
            | (Lead.linkedin_url.isnot(None))
        )
    )

    to_enrich = await db.execute(
        select(func.count(Lead.id)).where(Lead.status == LeadStatus.NEW)
    )

    return {
        "total_leads": total,
        "enriched": enriched,
        "to_enrich": to_enrich.scalar(),
        "with_email": with_email.scalar(),
        "with_phone": with_phone.scalar(),
        "with_social": with_social.scalar(),
        "enrichment_rate": round((enriched / total * 100) if total > 0 else 0, 1),
    }


@router.post("/batch")
@limiter.limit("5/minute")
async def enrich_leads_batch(
    request: Request,
    lead_ids: Optional[list[int]] = Query(
        None, description="IDs des leads à enrichir (optionnel)"
    ),
    limit: int = Query(10, ge=1, le=50, description="Nombre max de leads à enrichir"),
    status: LeadStatus = Query(
        LeadStatus.NEW, description="Statut des leads à enrichir"
    ),
    use_paid_apis: bool = Query(
        False, description="Utiliser les APIs payantes (Hunter.io, etc.)"
    ),
    db: AsyncSession = Depends(get_db),
):
    """
    Lance l'enrichissement en arrière-plan et retourne immédiatement un job_id.
    Suivre la progression via GET /enrichment/job/{job_id}
    """
    # Récupérer les IDs à enrichir
    if lead_ids:
        ids_to_enrich = lead_ids[:limit]
    else:
        query = select(Lead.id).where(Lead.status == status).limit(limit)
        result = await db.execute(query)
        ids_to_enrich = [row[0] for row in result.fetchall()]

    if not ids_to_enrich:
        return {"job_id": None, "total": 0, "message": "Aucun lead à enrichir"}

    job_id = str(uuid.uuid4())
    _jobs[job_id] = {
        "status": "pending",
        "total": len(ids_to_enrich),
        "current": 0,
        "results": [],
    }

    asyncio.create_task(_run_enrichment_job(job_id, ids_to_enrich, use_paid_apis))
    logger.info(f"Job d'enrichissement {job_id} lancé pour {len(ids_to_enrich)} leads")

    return {"job_id": job_id, "total": len(ids_to_enrich)}


@router.get("/job/{job_id}")
async def get_job_status(job_id: str):
    """Retourne la progression d'un job d'enrichissement."""
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job non trouvé")
    return job


@router.get("/status/{lead_id}")
async def get_enrichment_status(
    lead_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Retourne le statut d'enrichissement d'un lead.
    """
    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()

    if not lead:
        raise HTTPException(status_code=404, detail="Lead non trouvé")

    return {
        "lead_id": lead.id,
        "lead_name": lead.name,
        "status": lead.status.value,
        "enriched_at": lead.enriched_at.isoformat() if lead.enriched_at else None,
        "has_email": lead.email is not None,
        "has_phone": lead.phone is not None,
        "has_website": lead.website is not None,
        "has_social": any([lead.facebook_url, lead.instagram_url, lead.linkedin_url]),
        "data": {
            "email": lead.email,
            "phone": lead.phone,
            "website": lead.website,
            "facebook_url": lead.facebook_url,
            "instagram_url": lead.instagram_url,
            "linkedin_url": lead.linkedin_url,
        },
    }


@router.post("/{lead_id}")
async def enrich_single_lead(
    lead_id: int,
    use_paid_apis: bool = Query(
        False, description="Utiliser les APIs payantes (Hunter.io, etc.)"
    ),
    db: AsyncSession = Depends(get_db),
):
    """
    Enrichit un lead spécifique.

    Sources GRATUITES (par défaut) :
    - Site web de l'établissement (email, téléphone, réseaux sociaux)
    - PagesJaunes (téléphone, email)
    - Societe.com (noms des dirigeants)
    - DuckDuckGo (recherche email/contact)
    - Génération de patterns d'email (prenom.nom@domaine.com)

    Sources PAYANTES (optionnelles, use_paid_apis=true) :
    - Hunter.io (contacts avec emails vérifiés)
    """
    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()

    if not lead:
        raise HTTPException(status_code=404, detail="Lead non trouvé")

    logger.info(
        f"Enrichissement demandé pour: {lead.name} (APIs payantes: {use_paid_apis})"
    )

    service = EnrichmentService(db)
    try:
        enrichment_result = await service.enrich_lead(lead, use_paid_apis=use_paid_apis)
        return enrichment_result
    finally:
        await service.close()
