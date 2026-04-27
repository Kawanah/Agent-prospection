"""
Modèle Campaign - Représente une campagne de prospection.
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import String, Integer, DateTime, Text, Boolean, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class CampaignStatus(str, Enum):
    """Statut de la campagne."""

    DRAFT = "draft"  # Brouillon
    SCHEDULED = "scheduled"  # Planifiée
    RUNNING = "running"  # En cours
    PAUSED = "paused"  # En pause
    COMPLETED = "completed"  # Terminée
    CANCELLED = "cancelled"  # Annulée


class CampaignChannel(str, Enum):
    """Canal de la campagne."""

    EMAIL = "email"
    LINKEDIN = "linkedin"
    MULTI = "multi"  # Email + LinkedIn


class Campaign(Base):
    """
    Une campagne de prospection.
    Contient la configuration et le suivi d'une série de messages.
    """

    __tablename__ = "campaigns"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Identification
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text)

    # Configuration
    channel: Mapped[CampaignChannel] = mapped_column(
        SQLEnum(CampaignChannel), default=CampaignChannel.EMAIL
    )
    status: Mapped[CampaignStatus] = mapped_column(
        SQLEnum(CampaignStatus), default=CampaignStatus.DRAFT
    )

    # Ciblage
    target_lead_types: Mapped[Optional[str]] = mapped_column(
        String(500)
    )  # JSON list of LeadType
    target_regions: Mapped[Optional[str]] = mapped_column(
        String(500)
    )  # JSON list of regions
    min_score: Mapped[int] = mapped_column(Integer, default=0)

    # Templates de messages
    email_subject_template: Mapped[Optional[str]] = mapped_column(String(500))
    email_body_template: Mapped[Optional[str]] = mapped_column(Text)
    linkedin_message_template: Mapped[Optional[str]] = mapped_column(Text)

    # Configuration IA
    use_ai_generation: Mapped[bool] = mapped_column(Boolean, default=True)
    ai_personalization_level: Mapped[str] = mapped_column(
        String(50), default="medium"
    )  # low, medium, high

    # Séquençage
    follow_up_days: Mapped[int] = mapped_column(
        Integer, default=3
    )  # Jours entre les relances
    max_follow_ups: Mapped[int] = mapped_column(
        Integer, default=2
    )  # Nombre max de relances

    # Statistiques
    total_leads: Mapped[int] = mapped_column(Integer, default=0)
    emails_sent: Mapped[int] = mapped_column(Integer, default=0)
    emails_opened: Mapped[int] = mapped_column(Integer, default=0)
    emails_clicked: Mapped[int] = mapped_column(Integer, default=0)
    responses_received: Mapped[int] = mapped_column(Integer, default=0)
    positive_responses: Mapped[int] = mapped_column(Integer, default=0)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # Relations
    messages: Mapped[list["Message"]] = relationship(
        "Message", back_populates="campaign"
    )

    @property
    def open_rate(self) -> float:
        """Taux d'ouverture des emails."""
        if self.emails_sent == 0:
            return 0.0
        return (self.emails_opened / self.emails_sent) * 100

    @property
    def response_rate(self) -> float:
        """Taux de réponse."""
        if self.emails_sent == 0:
            return 0.0
        return (self.responses_received / self.emails_sent) * 100

    def __repr__(self) -> str:
        return f"<Campaign {self.id}: {self.name} ({self.status.value})>"
