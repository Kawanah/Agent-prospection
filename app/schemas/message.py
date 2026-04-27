"""
Schémas Pydantic pour les Messages.
Utilisés pour la validation des données d'entrée/sortie de l'API.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel

from app.models.message import (
    MessageChannel,
    MessageDirection,
    MessageStatus,
    SentimentType,
)


class MessageCreate(BaseModel):
    """Schéma pour créer un Message via l'API."""

    campaign_id: Optional[int] = None
    lead_id: int
    contact_id: Optional[int] = None
    channel: MessageChannel
    subject: Optional[str] = None
    body: str
    body_html: Optional[str] = None
    sequence_number: int = 1
    scheduled_at: Optional[datetime] = None


class MessageUpdate(BaseModel):
    """Schéma pour mettre à jour un Message."""

    status: Optional[MessageStatus] = None
    subject: Optional[str] = None
    body: Optional[str] = None
    body_html: Optional[str] = None
    scheduled_at: Optional[datetime] = None


class MessageResponse(BaseModel):
    """Schéma pour retourner un Message depuis l'API."""

    id: int
    campaign_id: Optional[int]
    lead_id: int
    contact_id: Optional[int]
    channel: MessageChannel
    direction: MessageDirection
    status: MessageStatus
    subject: Optional[str]
    body: str
    sequence_number: int
    sentiment: SentimentType
    sentiment_score: Optional[float]
    created_at: datetime
    scheduled_at: Optional[datetime]
    sent_at: Optional[datetime]
    opened_at: Optional[datetime]

    class Config:
        from_attributes = True


class MessageListResponse(BaseModel):
    """Réponse paginée pour la liste des messages."""

    total: int
    page: int
    per_page: int
    messages: list[MessageResponse]


class InboundMessage(BaseModel):
    """Schéma pour enregistrer une réponse reçue."""

    lead_id: int
    contact_id: Optional[int] = None
    channel: MessageChannel
    subject: Optional[str] = None
    body: str
    parent_message_id: Optional[int] = None
    received_at: Optional[datetime] = None


class SentimentAnalysis(BaseModel):
    """Résultat d'analyse de sentiment d'un message."""

    message_id: int
    sentiment: SentimentType
    sentiment_score: float
    analysis: str
    suggested_action: str
