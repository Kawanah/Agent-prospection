"""
API endpoints pour la gestion des Campaigns.
"""

from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from loguru import logger

from app.database import get_db
from app.models.campaign import Campaign, CampaignStatus, CampaignChannel
from app.schemas.campaign import (
    CampaignCreate,
    CampaignUpdate,
    CampaignResponse,
    CampaignStats,
    CampaignListResponse,
)
from app.models.lead import Lead, LeadStatus
from app.models.message import Message, MessageStatus, MessageDirection
from app.services.sequence_service import SequenceService

sequence_service = SequenceService()

router = APIRouter()


@router.get("/", response_model=CampaignListResponse)
async def list_campaigns(
    page: int = Query(1, ge=1, description="Numéro de page"),
    per_page: int = Query(20, ge=1, le=100, description="Campagnes par page"),
    status: Optional[CampaignStatus] = Query(None, description="Filtrer par statut"),
    channel: Optional[CampaignChannel] = Query(None, description="Filtrer par canal"),
    db: AsyncSession = Depends(get_db),
):
    """
    Liste les campagnes avec pagination et filtres.
    """
    query = select(Campaign)

    if status:
        query = query.where(Campaign.status == status)
    if channel:
        query = query.where(Campaign.channel == channel)

    # Compter le total
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # Pagination
    offset = (page - 1) * per_page
    query = query.order_by(Campaign.created_at.desc()).offset(offset).limit(per_page)

    result = await db.execute(query)
    campaigns = result.scalars().all()

    # Compter les messages QUEUED par campagne
    queued_counts_result = await db.execute(
        select(Message.campaign_id, func.count(Message.id))
        .where(
            Message.status == MessageStatus.QUEUED,
            Message.direction == MessageDirection.OUTBOUND,
        )
        .group_by(Message.campaign_id)
    )
    queued_by_campaign = {row[0]: row[1] for row in queued_counts_result.all()}

    def build_response(c: Campaign) -> CampaignResponse:
        data = CampaignResponse.model_validate(c)
        data.messages_queued = queued_by_campaign.get(c.id, 0)
        return data

    return CampaignListResponse(
        total=total,
        page=page,
        per_page=per_page,
        campaigns=[build_response(c) for c in campaigns],
    )


# ── Routes fixes (doivent être avant les routes dynamiques /{campaign_id}) ────


@router.get("/queue-stats")
async def get_queue_stats(db: AsyncSession = Depends(get_db)):
    """
    Retourne les statistiques de la file d'attente (messages en attente, quota, etc.)
    """
    return await sequence_service.get_queue_stats(db)


@router.post("/process-queue")
async def process_queue(db: AsyncSession = Depends(get_db)):
    """
    Traite la file d'attente : envoie les messages dont l'heure est venue.
    Respecte le quota journalier (50/jour) et le délai minimum (60s entre envois).
    """
    return await sequence_service.process_queue(db)


# ── Routes dynamiques ─────────────────────────────────────────────────────────


@router.get("/{campaign_id}", response_model=CampaignResponse)
async def get_campaign(campaign_id: int, db: AsyncSession = Depends(get_db)):
    """
    Récupère une campagne par son ID.
    """
    result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
    campaign = result.scalar_one_or_none()

    if not campaign:
        raise HTTPException(status_code=404, detail="Campagne non trouvée")

    return CampaignResponse.model_validate(campaign)


@router.get("/{campaign_id}/stats", response_model=CampaignStats)
async def get_campaign_stats(campaign_id: int, db: AsyncSession = Depends(get_db)):
    """
    Récupère les statistiques détaillées d'une campagne.
    """
    result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
    campaign = result.scalar_one_or_none()

    if not campaign:
        raise HTTPException(status_code=404, detail="Campagne non trouvée")

    # Calcul du taux de réponses positives
    positive_rate = 0.0
    if campaign.responses_received > 0:
        positive_rate = (
            campaign.positive_responses / campaign.responses_received
        ) * 100

    return CampaignStats(
        campaign_id=campaign.id,
        total_leads=campaign.total_leads,
        emails_sent=campaign.emails_sent,
        emails_opened=campaign.emails_opened,
        emails_clicked=campaign.emails_clicked,
        responses_received=campaign.responses_received,
        positive_responses=campaign.positive_responses,
        open_rate=campaign.open_rate,
        response_rate=campaign.response_rate,
        positive_rate=round(positive_rate, 1),
    )


@router.get("/{campaign_id}/preview-leads")
async def preview_campaign_leads(
    campaign_id: int,
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """
    Retourne les leads éligibles pour cette campagne (score > 0, email présent).
    Permet de prévisualiser qui recevra les messages avant de démarrer.
    """
    result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campagne non trouvée")

    leads_query = (
        select(Lead)
        .where(Lead.email.isnot(None), Lead.email != "")
        .where(Lead.status != LeadStatus.CONTACTED)
        .order_by(Lead.score.desc())
        .limit(limit)
    )
    leads_result = await db.execute(leads_query)
    leads = leads_result.scalars().all()

    return {
        "campaign_id": campaign_id,
        "campaign_name": campaign.name,
        "channel": campaign.channel.value,
        "eligible_count": len(leads),
        "leads": [
            {
                "id": l.id,
                "name": l.name,
                "city": l.city,
                "email": l.email,
                "score": l.score,
                "lead_type": l.lead_type.value if l.lead_type else None,
                "has_website": l.has_website,
            }
            for l in leads
        ],
    }


class AddLeadsRequest(BaseModel):
    lead_ids: list[int]


@router.post("/{campaign_id}/add-leads")
async def add_leads_to_campaign(
    campaign_id: int,
    body: AddLeadsRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Ajoute des leads spécifiques à une campagne et génère leurs messages.
    """
    result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
    campaign = result.scalar_one_or_none()

    if not campaign:
        raise HTTPException(status_code=404, detail="Campagne non trouvée")

    if campaign.status == CampaignStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail="Impossible d'ajouter des leads à une campagne terminée",
        )

    launch_result = await sequence_service.add_leads(campaign, body.lead_ids, db)
    logger.info(
        f"Campagne {campaign.name} — {launch_result['queued']} leads ajoutés manuellement"
    )
    return launch_result


@router.post("/", response_model=CampaignResponse, status_code=201)
async def create_campaign(
    campaign_data: CampaignCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Crée une nouvelle campagne.
    """
    campaign = Campaign(**campaign_data.model_dump())
    db.add(campaign)
    await db.commit()
    await db.refresh(campaign)

    logger.info(f"Campagne créée: {campaign.name}")
    return CampaignResponse.model_validate(campaign)


@router.patch("/{campaign_id}", response_model=CampaignResponse)
async def update_campaign(
    campaign_id: int,
    campaign_data: CampaignUpdate,
    db: AsyncSession = Depends(get_db),
):
    """
    Met à jour une campagne.
    """
    result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
    campaign = result.scalar_one_or_none()

    if not campaign:
        raise HTTPException(status_code=404, detail="Campagne non trouvée")

    # Mise à jour des champs fournis
    update_data = campaign_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(campaign, field, value)

    await db.commit()
    await db.refresh(campaign)

    return CampaignResponse.model_validate(campaign)


@router.post("/{campaign_id}/start")
async def start_campaign(
    campaign_id: int,
    limit: Optional[int] = Query(None, description="Nombre max de leads à traiter"),
    db: AsyncSession = Depends(get_db),
):
    """
    Démarre une campagne : génère et planifie les messages pour tous les leads éligibles.
    """
    result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
    campaign = result.scalar_one_or_none()

    if not campaign:
        raise HTTPException(status_code=404, detail="Campagne non trouvée")

    if campaign.status not in (CampaignStatus.DRAFT, CampaignStatus.PAUSED):
        raise HTTPException(
            status_code=400,
            detail=f"Impossible de démarrer une campagne en statut {campaign.status.value}",
        )

    campaign.status = CampaignStatus.RUNNING
    campaign.started_at = campaign.started_at or datetime.utcnow()
    await db.commit()

    # Générer et planifier les messages
    launch_result = await sequence_service.launch_campaign(campaign, db, limit=limit)

    logger.info(
        f"Campagne {campaign.name} démarrée — {launch_result['queued']} messages planifiés"
    )
    return {
        "message": f"Campagne {campaign.name} démarrée",
        "status": "running",
        **launch_result,
    }


@router.post("/{campaign_id}/pause")
async def pause_campaign(campaign_id: int, db: AsyncSession = Depends(get_db)):
    """
    Met en pause une campagne.
    """
    result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
    campaign = result.scalar_one_or_none()

    if not campaign:
        raise HTTPException(status_code=404, detail="Campagne non trouvée")

    if campaign.status != CampaignStatus.RUNNING:
        raise HTTPException(
            status_code=400,
            detail="Seule une campagne en cours peut être mise en pause",
        )

    campaign.status = CampaignStatus.PAUSED
    await db.commit()

    logger.info(f"Campagne {campaign.name} mise en pause")
    return {"message": f"Campagne {campaign.name} mise en pause", "status": "paused"}


@router.post("/{campaign_id}/stop")
async def stop_campaign(campaign_id: int, db: AsyncSession = Depends(get_db)):
    """
    Arrête définitivement une campagne.
    """
    result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
    campaign = result.scalar_one_or_none()

    if not campaign:
        raise HTTPException(status_code=404, detail="Campagne non trouvée")

    campaign.status = CampaignStatus.COMPLETED
    campaign.completed_at = datetime.utcnow()
    await db.commit()

    logger.info(f"Campagne {campaign.name} terminée")
    return {"message": f"Campagne {campaign.name} terminée", "status": "completed"}


@router.delete("/{campaign_id}/leads/{lead_id}")
async def remove_lead_from_campaign(
    campaign_id: int,
    lead_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Retire un lead d'une campagne : supprime tous ses messages QUEUED.
    Les messages déjà envoyés ne sont pas touchés.
    """
    result = await db.execute(
        select(Message).where(
            Message.campaign_id == campaign_id,
            Message.lead_id == lead_id,
            Message.status == MessageStatus.QUEUED,
        )
    )
    messages = result.scalars().all()

    if not messages:
        raise HTTPException(
            status_code=404,
            detail="Aucun message annulable pour ce lead (déjà envoyé ou inexistant)",
        )

    count = len(messages)
    for msg in messages:
        await db.delete(msg)
    await db.commit()

    logger.info(
        f"Lead {lead_id} retiré de la campagne {campaign_id} — {count} message(s) supprimé(s)"
    )
    return {"message": f"{count} message(s) annulé(s)", "removed": count}


@router.delete("/{campaign_id}")
async def delete_campaign(campaign_id: int, db: AsyncSession = Depends(get_db)):
    """
    Supprime une campagne.
    """
    result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
    campaign = result.scalar_one_or_none()

    if not campaign:
        raise HTTPException(status_code=404, detail="Campagne non trouvée")

    if campaign.status == CampaignStatus.RUNNING:
        raise HTTPException(
            status_code=400,
            detail="Impossible de supprimer une campagne en cours. Arrêtez-la d'abord.",
        )

    await db.delete(campaign)
    await db.commit()

    return {"message": f"Campagne {campaign_id} supprimée"}
