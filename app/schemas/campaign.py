"""
Schémas Pydantic pour les Campaigns.
Utilisés pour la validation des données d'entrée/sortie de l'API.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

from app.models.campaign import CampaignStatus, CampaignChannel


class CampaignCreate(BaseModel):
    """Schéma pour créer une Campaign via l'API."""

    name: str
    description: Optional[str] = None
    channel: CampaignChannel = CampaignChannel.EMAIL

    # Ciblage
    target_lead_types: Optional[str] = None
    target_regions: Optional[str] = None
    min_score: int = 0

    # Templates
    email_subject_template: Optional[str] = None
    email_body_template: Optional[str] = None
    linkedin_message_template: Optional[str] = None

    # Configuration IA
    use_ai_generation: bool = True
    ai_personalization_level: str = "medium"

    # Séquençage
    follow_up_days: int = 3
    max_follow_ups: int = 2


class CampaignUpdate(BaseModel):
    """Schéma pour mettre à jour une Campaign."""

    name: Optional[str] = None
    description: Optional[str] = None
    channel: Optional[CampaignChannel] = None
    status: Optional[CampaignStatus] = None

    target_lead_types: Optional[str] = None
    target_regions: Optional[str] = None
    min_score: Optional[int] = None

    email_subject_template: Optional[str] = None
    email_body_template: Optional[str] = None
    linkedin_message_template: Optional[str] = None

    use_ai_generation: Optional[bool] = None
    ai_personalization_level: Optional[str] = None

    follow_up_days: Optional[int] = None
    max_follow_ups: Optional[int] = None


class CampaignResponse(BaseModel):
    """Schéma pour retourner une Campaign depuis l'API."""

    id: int
    name: str
    description: Optional[str]
    channel: CampaignChannel
    status: CampaignStatus

    # Ciblage
    target_lead_types: Optional[str]
    target_regions: Optional[str]
    min_score: int

    # Configuration IA
    use_ai_generation: bool
    ai_personalization_level: str

    # Séquençage
    follow_up_days: int
    max_follow_ups: int

    # Statistiques
    total_leads: int
    emails_sent: int
    emails_opened: int
    responses_received: int
    positive_responses: int
    messages_queued: int = 0  # messages planifiés, pas encore envoyés

    # Timestamps
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True


class CampaignStats(BaseModel):
    """Statistiques détaillées d'une campagne."""

    campaign_id: int
    total_leads: int
    emails_sent: int
    emails_opened: int
    emails_clicked: int
    responses_received: int
    positive_responses: int
    open_rate: float
    response_rate: float
    positive_rate: float


class CampaignListResponse(BaseModel):
    """Réponse paginée pour la liste des campagnes."""

    total: int
    page: int
    per_page: int
    campaigns: list[CampaignResponse]
