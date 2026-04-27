"""
API endpoints pour la gestion des Messages.
"""

from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from loguru import logger
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

from pydantic import BaseModel as PydanticBaseModel

from app.database import get_db
from app.models.message import (
    Message,
    MessageChannel,
    MessageDirection,
    MessageStatus,
    SentimentType,
)
from app.models.lead import Lead
from app.models.contact import Contact
from app.services.email_service import EmailService
from app.models.campaign import Campaign
from app.schemas.message import (
    MessageCreate,
    MessageUpdate,
    MessageResponse,
    MessageListResponse,
    InboundMessage,
)

router = APIRouter()


@router.get("/", response_model=MessageListResponse)
async def list_messages(
    page: int = Query(1, ge=1, description="Numéro de page"),
    per_page: int = Query(20, ge=1, le=100, description="Messages par page"),
    campaign_id: Optional[int] = Query(None, description="Filtrer par campagne"),
    lead_id: Optional[int] = Query(None, description="Filtrer par lead"),
    channel: Optional[MessageChannel] = Query(None, description="Filtrer par canal"),
    direction: Optional[MessageDirection] = Query(
        None, description="Filtrer par direction"
    ),
    status: Optional[MessageStatus] = Query(None, description="Filtrer par statut"),
    db: AsyncSession = Depends(get_db),
):
    """
    Liste les messages avec pagination et filtres.
    """
    query = select(Message)

    if campaign_id:
        query = query.where(Message.campaign_id == campaign_id)
    if lead_id:
        query = query.where(Message.lead_id == lead_id)
    if channel:
        query = query.where(Message.channel == channel)
    if direction:
        query = query.where(Message.direction == direction)
    if status:
        query = query.where(Message.status == status)

    # Compter le total
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # Pagination
    offset = (page - 1) * per_page
    query = query.order_by(Message.created_at.desc()).offset(offset).limit(per_page)

    result = await db.execute(query)
    messages = result.scalars().all()

    return MessageListResponse(
        total=total,
        page=page,
        per_page=per_page,
        messages=[MessageResponse.model_validate(m) for m in messages],
    )


@router.get("/{message_id}", response_model=MessageResponse)
async def get_message(message_id: int, db: AsyncSession = Depends(get_db)):
    """
    Récupère un message par son ID.
    """
    result = await db.execute(select(Message).where(Message.id == message_id))
    message = result.scalar_one_or_none()

    if not message:
        raise HTTPException(status_code=404, detail="Message non trouvé")

    return MessageResponse.model_validate(message)


@router.post("/", response_model=MessageResponse, status_code=201)
async def create_message(
    message_data: MessageCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Crée un nouveau message (brouillon).
    """
    # Vérifier que le lead existe
    lead_result = await db.execute(select(Lead).where(Lead.id == message_data.lead_id))
    if not lead_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Lead non trouvé")

    # Vérifier le contact si fourni
    if message_data.contact_id:
        contact_result = await db.execute(
            select(Contact).where(Contact.id == message_data.contact_id)
        )
        if not contact_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Contact non trouvé")

    # Vérifier la campagne si fournie
    if message_data.campaign_id:
        campaign_result = await db.execute(
            select(Campaign).where(Campaign.id == message_data.campaign_id)
        )
        if not campaign_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Campagne non trouvée")

    message = Message(
        **message_data.model_dump(),
        direction=MessageDirection.OUTBOUND,
        status=MessageStatus.DRAFT,
    )
    db.add(message)
    await db.commit()
    await db.refresh(message)

    logger.info(f"Message créé: {message.id} pour lead {message.lead_id}")
    return MessageResponse.model_validate(message)


@router.post("/inbound", response_model=MessageResponse, status_code=201)
async def register_inbound_message(
    message_data: InboundMessage,
    db: AsyncSession = Depends(get_db),
):
    """
    Enregistre une réponse reçue d'un prospect.
    """
    # Vérifier que le lead existe
    lead_result = await db.execute(select(Lead).where(Lead.id == message_data.lead_id))
    if not lead_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Lead non trouvé")

    message = Message(
        lead_id=message_data.lead_id,
        contact_id=message_data.contact_id,
        channel=message_data.channel,
        direction=MessageDirection.INBOUND,
        status=MessageStatus.DELIVERED,
        subject=message_data.subject,
        body=message_data.body,
        parent_message_id=message_data.parent_message_id,
        received_at=message_data.received_at or datetime.utcnow(),
        sentiment=SentimentType.UNKNOWN,
    )
    db.add(message)

    # Incrémenter le compteur de réponses si lié à un message parent avec campagne
    if message_data.parent_message_id:
        parent_result = await db.execute(
            select(Message).where(Message.id == message_data.parent_message_id)
        )
        parent = parent_result.scalar_one_or_none()
        if parent and parent.campaign_id:
            campaign_result = await db.execute(
                select(Campaign).where(Campaign.id == parent.campaign_id)
            )
            campaign = campaign_result.scalar_one_or_none()
            if campaign:
                campaign.responses_received += 1

    await db.commit()
    await db.refresh(message)

    logger.info(f"Réponse enregistrée: {message.id} du lead {message.lead_id}")
    return MessageResponse.model_validate(message)


@router.patch("/{message_id}", response_model=MessageResponse)
async def update_message(
    message_id: int,
    message_data: MessageUpdate,
    db: AsyncSession = Depends(get_db),
):
    """
    Met à jour un message.
    """
    result = await db.execute(select(Message).where(Message.id == message_id))
    message = result.scalar_one_or_none()

    if not message:
        raise HTTPException(status_code=404, detail="Message non trouvé")

    update_data = message_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(message, field, value)

    await db.commit()
    await db.refresh(message)

    return MessageResponse.model_validate(message)


@router.post("/{message_id}/queue")
async def queue_message(message_id: int, db: AsyncSession = Depends(get_db)):
    """
    Met un message en file d'attente pour envoi.
    """
    result = await db.execute(select(Message).where(Message.id == message_id))
    message = result.scalar_one_or_none()

    if not message:
        raise HTTPException(status_code=404, detail="Message non trouvé")

    if message.status != MessageStatus.DRAFT:
        raise HTTPException(
            status_code=400,
            detail=f"Seul un brouillon peut être mis en file d'attente (statut actuel: {message.status.value})",
        )

    message.status = MessageStatus.QUEUED
    await db.commit()

    return {
        "message": f"Message {message_id} mis en file d'attente",
        "status": "queued",
    }


@router.post("/{message_id}/mark-sent")
async def mark_message_sent(message_id: int, db: AsyncSession = Depends(get_db)):
    """
    Marque un message comme envoyé.
    """
    result = await db.execute(select(Message).where(Message.id == message_id))
    message = result.scalar_one_or_none()

    if not message:
        raise HTTPException(status_code=404, detail="Message non trouvé")

    message.status = MessageStatus.SENT
    message.sent_at = datetime.utcnow()

    # Incrémenter le compteur de la campagne associée
    if message.campaign_id:
        campaign_result = await db.execute(
            select(Campaign).where(Campaign.id == message.campaign_id)
        )
        campaign = campaign_result.scalar_one_or_none()
        if campaign:
            campaign.emails_sent += 1

    await db.commit()

    return {"message": f"Message {message_id} marqué comme envoyé", "status": "sent"}


@router.post("/{message_id}/mark-opened")
async def mark_message_opened(message_id: int, db: AsyncSession = Depends(get_db)):
    """
    Marque un message comme ouvert (tracking).
    """
    result = await db.execute(select(Message).where(Message.id == message_id))
    message = result.scalar_one_or_none()

    if not message:
        raise HTTPException(status_code=404, detail="Message non trouvé")

    message.status = MessageStatus.OPENED
    message.opened_at = datetime.utcnow()

    # Incrémenter le compteur de la campagne associée
    if message.campaign_id:
        campaign_result = await db.execute(
            select(Campaign).where(Campaign.id == message.campaign_id)
        )
        campaign = campaign_result.scalar_one_or_none()
        if campaign:
            campaign.emails_opened += 1

    await db.commit()

    return {"message": f"Message {message_id} marqué comme ouvert", "status": "opened"}


@router.delete("/{message_id}")
async def delete_message(message_id: int, db: AsyncSession = Depends(get_db)):
    """
    Supprime un message.
    """
    result = await db.execute(select(Message).where(Message.id == message_id))
    message = result.scalar_one_or_none()

    if not message:
        raise HTTPException(status_code=404, detail="Message non trouvé")

    if message.status in (MessageStatus.SENT, MessageStatus.DELIVERED):
        raise HTTPException(
            status_code=400, detail="Impossible de supprimer un message déjà envoyé"
        )

    await db.delete(message)
    await db.commit()

    return {"message": f"Message {message_id} supprimé"}


class SendTestRequest(PydanticBaseModel):
    to_email: str


@router.post("/{message_id}/send-test")
@limiter.limit("5/minute")
async def send_message_test(
    request: Request,
    message_id: int,
    data: SendTestRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Envoie un message existant vers un email de beta test.
    N'affecte pas le statut du message ni du lead.
    """
    result = await db.execute(select(Message).where(Message.id == message_id))
    message = result.scalar_one_or_none()

    if not message:
        raise HTTPException(status_code=404, detail="Message non trouvé")

    if not message.body:
        raise HTTPException(status_code=400, detail="Ce message n'a pas de corps")

    service = EmailService()
    if not service.is_configured():
        raise HTTPException(
            status_code=400,
            detail="Configuration SMTP incomplète. Configurez le SMTP dans les Paramètres.",
        )

    subject = f"[TEST] {message.subject or 'Message de prospection'}"
    body = f"⚠️ EMAIL DE TEST — ce message aurait été envoyé à un vrai prospect.\n\n{'─' * 50}\n\n{message.body}"

    email_result = service.send_email(
        to_email=data.to_email, subject=subject, body=body
    )

    if not email_result.success:
        raise HTTPException(status_code=500, detail=email_result.error)

    logger.info(f"Message {message_id} envoyé en test à {data.to_email}")
    return {"success": True, "message": f"Message envoyé en test à {data.to_email}"}


@router.get("/by-lead/{lead_id}", response_model=list[MessageResponse])
async def get_messages_by_lead(lead_id: int, db: AsyncSession = Depends(get_db)):
    """
    Récupère tous les messages d'un lead (envoyés et reçus).
    """
    lead_result = await db.execute(select(Lead).where(Lead.id == lead_id))
    if not lead_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Lead non trouvé")

    result = await db.execute(
        select(Message)
        .where(Message.lead_id == lead_id)
        .order_by(Message.created_at.asc())
    )
    messages = result.scalars().all()

    return [MessageResponse.model_validate(m) for m in messages]
