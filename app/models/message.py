"""
Modèle Message - Représente un message envoyé ou reçu.
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import String, Integer, DateTime, Text, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class MessageChannel(str, Enum):
    """Canal du message."""

    EMAIL = "email"
    LINKEDIN = "linkedin"


class MessageDirection(str, Enum):
    """Direction du message."""

    OUTBOUND = "outbound"  # Message envoyé
    INBOUND = "inbound"  # Réponse reçue


class MessageStatus(str, Enum):
    """Statut du message."""

    DRAFT = "draft"  # Brouillon
    QUEUED = "queued"  # En file d'attente
    SENT = "sent"  # Envoyé
    DELIVERED = "delivered"  # Délivré
    OPENED = "opened"  # Ouvert
    CLICKED = "clicked"  # Lien cliqué
    REPLIED = "replied"  # Réponse reçue
    BOUNCED = "bounced"  # Rebond (erreur)
    FAILED = "failed"  # Échec d'envoi


class SentimentType(str, Enum):
    """Sentiment détecté dans une réponse."""

    POSITIVE = "positive"  # Intéressé
    NEUTRAL = "neutral"  # Neutre / Question
    NEGATIVE = "negative"  # Pas intéressé / Refus
    UNKNOWN = "unknown"  # Non analysé


class Message(Base):
    """
    Un message dans une campagne de prospection.
    Peut être un message envoyé ou une réponse reçue.
    """

    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Relations
    campaign_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("campaigns.id"), index=True
    )
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id"), index=True)
    contact_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("contacts.id"), index=True
    )

    # Type de message
    channel: Mapped[MessageChannel] = mapped_column(SQLEnum(MessageChannel))
    direction: Mapped[MessageDirection] = mapped_column(
        SQLEnum(MessageDirection), default=MessageDirection.OUTBOUND
    )
    status: Mapped[MessageStatus] = mapped_column(
        SQLEnum(MessageStatus), default=MessageStatus.DRAFT
    )

    # Contenu
    subject: Mapped[Optional[str]] = mapped_column(String(500))  # Pour les emails
    body: Mapped[str] = mapped_column(Text)
    body_html: Mapped[Optional[str]] = mapped_column(
        Text
    )  # Version HTML pour les emails

    # Séquençage
    sequence_number: Mapped[int] = mapped_column(
        Integer, default=1
    )  # 1 = premier contact, 2+ = relances
    parent_message_id: Mapped[Optional[int]] = mapped_column(ForeignKey("messages.id"))

    # Analyse des réponses
    sentiment: Mapped[SentimentType] = mapped_column(
        SQLEnum(SentimentType), default=SentimentType.UNKNOWN
    )
    sentiment_score: Mapped[Optional[float]] = mapped_column()  # -1.0 à 1.0
    ai_analysis: Mapped[Optional[str]] = mapped_column(Text)  # Analyse complète par IA

    # Tracking
    external_id: Mapped[Optional[str]] = mapped_column(
        String(255)
    )  # ID du provider (SendGrid, etc.)
    opened_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    clicked_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    scheduled_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    received_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime
    )  # Pour les réponses

    # Relations
    campaign: Mapped[Optional["Campaign"]] = relationship(
        "Campaign", back_populates="messages"
    )
    lead: Mapped["Lead"] = relationship("Lead", back_populates="messages")
    contact: Mapped[Optional["Contact"]] = relationship(
        "Contact", back_populates="messages"
    )

    def __repr__(self) -> str:
        return f"<Message {self.id}: {self.channel.value} {self.direction.value} ({self.status.value})>"
