"""
API endpoints pour le scoring et la priorisation des leads.
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.scoring_service import (
    ScoringService,
    analyze_lead_by_id,
)

router = APIRouter()


@router.post("/analyze/{lead_id}")
async def analyze_lead(
    lead_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Analyse le site web d'un lead et met à jour ses scores.

    Retourne les scores :
    - quality_score : qualité du site (0-100)
    - seo_score : optimisation SEO (0-100)
    - geo_score : optimisation pour les IA (0-100)
    - score : score de priorité global (0-100)
    """
    result = await analyze_lead_by_id(db, lead_id)

    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])

    return result


@router.post("/analyze/batch")
async def analyze_leads_batch(
    lead_ids: Optional[list[int]] = None,
    limit: int = Query(default=10, le=50, description="Nombre max de leads à analyser"),
    only_unanalyzed: bool = Query(
        default=True, description="Analyser uniquement les leads sans score"
    ),
    db: AsyncSession = Depends(get_db),
):
    """
    Analyse plusieurs leads en batch.

    - Si lead_ids est fourni, analyse ces leads spécifiques
    - Sinon, analyse les leads non encore analysés (jusqu'à limit)
    """
    service = ScoringService(db)
    try:
        return await service.analyze_leads_batch(
            lead_ids=lead_ids,
            limit=limit,
            only_unanalyzed=only_unanalyzed,
        )
    finally:
        await service.close()


@router.get("/priority")
async def get_leads_by_priority(
    segment: Optional[str] = Query(
        default=None, description="Segment: 'hot' (>=80), 'warm' (50-79), 'cold' (<50)"
    ),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """
    Récupère les leads triés par score de priorité.

    Segments disponibles :
    - hot : Score >= 80 (prospects prioritaires 🔥)
    - warm : Score 50-79 (prospects tièdes 😐)
    - cold : Score < 50 (prospects froids ❄️)
    """
    if segment and segment not in ["hot", "warm", "cold"]:
        raise HTTPException(
            status_code=400, detail="Segment invalide. Utilisez 'hot', 'warm' ou 'cold'"
        )

    service = ScoringService(db)
    return await service.get_leads_by_priority(
        segment=segment,
        limit=limit,
        offset=offset,
    )


@router.get("/stats")
async def get_scoring_stats(
    db: AsyncSession = Depends(get_db),
):
    """
    Retourne les statistiques de scoring :
    - Nombre total de leads
    - Répartition par segment (hot/warm/cold)
    - Nombre de leads analysés vs en attente
    - Score moyen
    """
    service = ScoringService(db)
    return await service.get_scoring_stats()


@router.post("/recalculate")
async def recalculate_all_scores(
    limit: int = Query(
        default=500, le=10000, description="Nombre de leads à recalculer"
    ),
    db: AsyncSession = Depends(get_db),
):
    """
    Recalcule le score de priorité de tous les leads.
    Utile après une modification de l'algorithme de scoring.
    """
    from sqlalchemy import select
    from app.models.lead import Lead

    result = await db.execute(select(Lead).limit(limit))
    leads = result.scalars().all()

    updated = 0
    for lead in leads:
        old_score = lead.score
        lead.update_score()
        if lead.score != old_score:
            updated += 1

    await db.commit()

    return {
        "total_processed": len(leads),
        "scores_updated": updated,
        "message": f"{updated} leads ont eu leur score mis à jour",
    }
