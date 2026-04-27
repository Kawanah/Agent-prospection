"""
API endpoints pour l'analyse des avis Google.
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from loguru import logger
from pydantic import BaseModel
from datetime import datetime

from app.database import get_db
from app.models.lead import Lead
from app.services.google_reviews_service import get_google_reviews_service


router = APIRouter()


# Schémas Pydantic pour les réponses
class GoogleReviewsResponse(BaseModel):
    """Réponse de l'analyse des avis Google."""

    lead_id: int
    lead_name: str
    place_id: Optional[str]
    rating: Optional[float]
    reviews_count: Optional[int]
    period_months: Optional[int]
    frequency: Optional[float]  # Avis par mois
    trend: Optional[str]  # "growing", "stable", "declining"
    analyzed_at: Optional[datetime]
    message: str


class ReviewsStatsResponse(BaseModel):
    """Statistiques globales des avis."""

    total_analyzed: int
    average_rating: float
    average_frequency: float
    by_trend: dict
    top_rated: list
    most_reviewed: list


@router.post("/{lead_id}/analyze", response_model=GoogleReviewsResponse)
async def analyze_lead_reviews(
    lead_id: int,
    force: bool = Query(False, description="Forcer la réanalyse même si déjà analysé"),
    db: AsyncSession = Depends(get_db),
):
    """
    Analyse les avis Google d'un lead.

    Récupère les données depuis l'API Google Places :
    - Note moyenne
    - Nombre d'avis
    - Fréquence (avis par mois)
    - Tendance (croissance/stable/déclin)
    """
    # Récupérer le lead
    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()

    if not lead:
        raise HTTPException(status_code=404, detail="Lead non trouvé")

    # Vérifier si déjà analysé (sauf si force=True)
    if lead.google_reviews_analyzed_at and not force:
        return GoogleReviewsResponse(
            lead_id=lead.id,
            lead_name=lead.name,
            place_id=lead.google_place_id,
            rating=lead.google_rating,
            reviews_count=lead.google_reviews_count,
            period_months=lead.google_reviews_period_months,
            frequency=lead.google_reviews_frequency,
            trend=lead.google_reviews_trend,
            analyzed_at=lead.google_reviews_analyzed_at,
            message="Données déjà analysées (utilisez force=true pour réanalyser)",
        )

    # Lancer l'analyse
    service = get_google_reviews_service()

    try:
        reviews_data = await service.analyze_establishment(
            name=lead.name,
            city=lead.city,
            address=lead.address,
            place_id=lead.google_place_id,
        )

        if not reviews_data:
            return GoogleReviewsResponse(
                lead_id=lead.id,
                lead_name=lead.name,
                place_id=None,
                rating=None,
                reviews_count=None,
                period_months=None,
                frequency=None,
                trend=None,
                analyzed_at=None,
                message="Établissement non trouvé sur Google Maps",
            )

        # Mettre à jour le lead avec les données
        lead.google_place_id = reviews_data.place_id
        lead.google_rating = reviews_data.rating
        lead.google_reviews_count = reviews_data.reviews_count
        lead.google_reviews_period_months = reviews_data.period_months
        lead.google_reviews_frequency = reviews_data.frequency
        lead.google_reviews_trend = reviews_data.trend
        lead.google_reviews_analyzed_at = reviews_data.analyzed_at

        # Recalculer le score du lead
        lead.update_score()

        await db.commit()
        await db.refresh(lead)

        logger.info(
            f"Avis Google analysés pour {lead.name}: {reviews_data.reviews_count} avis, note {reviews_data.rating}"
        )

        return GoogleReviewsResponse(
            lead_id=lead.id,
            lead_name=lead.name,
            place_id=reviews_data.place_id,
            rating=reviews_data.rating,
            reviews_count=reviews_data.reviews_count,
            period_months=reviews_data.period_months,
            frequency=reviews_data.frequency,
            trend=reviews_data.trend,
            analyzed_at=reviews_data.analyzed_at,
            message="Analyse terminée avec succès",
        )

    except Exception as e:
        logger.error(f"Erreur lors de l'analyse des avis pour {lead.name}: {e}")
        raise HTTPException(
            status_code=500, detail=f"Erreur lors de l'analyse: {str(e)}"
        )


@router.get("/{lead_id}", response_model=GoogleReviewsResponse)
async def get_lead_reviews(
    lead_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Récupère les données d'avis Google déjà analysées pour un lead.
    """
    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()

    if not lead:
        raise HTTPException(status_code=404, detail="Lead non trouvé")

    if not lead.google_reviews_analyzed_at:
        return GoogleReviewsResponse(
            lead_id=lead.id,
            lead_name=lead.name,
            place_id=None,
            rating=None,
            reviews_count=None,
            period_months=None,
            frequency=None,
            trend=None,
            analyzed_at=None,
            message="Avis non encore analysés. Utilisez POST /analyze pour lancer l'analyse.",
        )

    return GoogleReviewsResponse(
        lead_id=lead.id,
        lead_name=lead.name,
        place_id=lead.google_place_id,
        rating=lead.google_rating,
        reviews_count=lead.google_reviews_count,
        period_months=lead.google_reviews_period_months,
        frequency=lead.google_reviews_frequency,
        trend=lead.google_reviews_trend,
        analyzed_at=lead.google_reviews_analyzed_at,
        message="OK",
    )


@router.post("/batch")
async def analyze_batch(
    limit: int = Query(10, ge=1, le=100, description="Nombre de leads à analyser"),
    only_unanalyzed: bool = Query(
        True, description="Uniquement les leads non analysés"
    ),
    db: AsyncSession = Depends(get_db),
):
    """
    Analyse les avis Google pour plusieurs leads en batch.

    Utile pour enrichir automatiquement la base de données.
    """
    query = select(Lead)

    if only_unanalyzed:
        query = query.where(Lead.google_reviews_analyzed_at == None)

    query = query.order_by(Lead.score.desc()).limit(limit)

    result = await db.execute(query)
    leads = result.scalars().all()

    if not leads:
        return {"message": "Aucun lead à analyser", "analyzed": 0, "results": []}

    service = get_google_reviews_service()
    results = []

    for lead in leads:
        try:
            reviews_data = await service.analyze_establishment(
                name=lead.name, city=lead.city, address=lead.address
            )

            if reviews_data:
                lead.google_place_id = reviews_data.place_id
                lead.google_rating = reviews_data.rating
                lead.google_reviews_count = reviews_data.reviews_count
                lead.google_reviews_period_months = reviews_data.period_months
                lead.google_reviews_frequency = reviews_data.frequency
                lead.google_reviews_trend = reviews_data.trend
                lead.google_reviews_analyzed_at = reviews_data.analyzed_at
                lead.update_score()

                results.append(
                    {
                        "lead_id": lead.id,
                        "name": lead.name,
                        "status": "success",
                        "rating": reviews_data.rating,
                        "reviews_count": reviews_data.reviews_count,
                    }
                )
            else:
                results.append(
                    {"lead_id": lead.id, "name": lead.name, "status": "not_found"}
                )

        except Exception as e:
            logger.error(f"Erreur batch pour {lead.name}: {e}")
            results.append(
                {
                    "lead_id": lead.id,
                    "name": lead.name,
                    "status": "error",
                    "error": str(e),
                }
            )

    await db.commit()

    success_count = len([r for r in results if r["status"] == "success"])
    logger.info(f"Batch terminé: {success_count}/{len(results)} leads analysés")

    return {
        "message": f"Analyse batch terminée",
        "analyzed": success_count,
        "total": len(results),
        "results": results,
    }


@router.get("/stats/overview", response_model=ReviewsStatsResponse)
async def get_reviews_stats(db: AsyncSession = Depends(get_db)):
    """
    Retourne les statistiques globales des avis Google.
    """
    # Nombre de leads analysés
    analyzed_result = await db.execute(
        select(func.count(Lead.id)).where(Lead.google_reviews_analyzed_at != None)
    )
    total_analyzed = analyzed_result.scalar() or 0

    # Note moyenne
    avg_rating_result = await db.execute(
        select(func.avg(Lead.google_rating)).where(Lead.google_rating != None)
    )
    average_rating = round(avg_rating_result.scalar() or 0, 2)

    # Fréquence moyenne
    avg_freq_result = await db.execute(
        select(func.avg(Lead.google_reviews_frequency)).where(
            Lead.google_reviews_frequency != None
        )
    )
    average_frequency = round(avg_freq_result.scalar() or 0, 2)

    # Par tendance
    trend_query = (
        select(Lead.google_reviews_trend, func.count(Lead.id))
        .where(Lead.google_reviews_trend != None)
        .group_by(Lead.google_reviews_trend)
    )

    trend_result = await db.execute(trend_query)
    by_trend = {row[0]: row[1] for row in trend_result}

    # Top rated (5 meilleurs)
    top_rated_result = await db.execute(
        select(Lead.id, Lead.name, Lead.google_rating)
        .where(Lead.google_rating != None)
        .order_by(Lead.google_rating.desc())
        .limit(5)
    )
    top_rated = [{"id": r[0], "name": r[1], "rating": r[2]} for r in top_rated_result]

    # Most reviewed (5 plus commentés)
    most_reviewed_result = await db.execute(
        select(Lead.id, Lead.name, Lead.google_reviews_count)
        .where(Lead.google_reviews_count != None)
        .order_by(Lead.google_reviews_count.desc())
        .limit(5)
    )
    most_reviewed = [
        {"id": r[0], "name": r[1], "count": r[2]} for r in most_reviewed_result
    ]

    return ReviewsStatsResponse(
        total_analyzed=total_analyzed,
        average_rating=average_rating,
        average_frequency=average_frequency,
        by_trend=by_trend,
        top_rated=top_rated,
        most_reviewed=most_reviewed,
    )
