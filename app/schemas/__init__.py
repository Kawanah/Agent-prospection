"""
Schémas Pydantic pour la validation des données.
"""

from app.schemas.lead import (
    LeadImportRow,
    LeadCreate,
    LeadResponse,
    LeadListResponse,
    ImportResult,
)

from app.schemas.contact import (
    ContactCreate,
    ContactUpdate,
    ContactResponse,
    ContactListResponse,
)

from app.schemas.campaign import (
    CampaignCreate,
    CampaignUpdate,
    CampaignResponse,
    CampaignStats,
    CampaignListResponse,
)

from app.schemas.message import (
    MessageCreate,
    MessageUpdate,
    MessageResponse,
    MessageListResponse,
    InboundMessage,
    SentimentAnalysis,
)

__all__ = [
    # Lead
    "LeadImportRow",
    "LeadCreate",
    "LeadResponse",
    "LeadListResponse",
    "ImportResult",
    # Contact
    "ContactCreate",
    "ContactUpdate",
    "ContactResponse",
    "ContactListResponse",
    # Campaign
    "CampaignCreate",
    "CampaignUpdate",
    "CampaignResponse",
    "CampaignStats",
    "CampaignListResponse",
    # Message
    "MessageCreate",
    "MessageUpdate",
    "MessageResponse",
    "MessageListResponse",
    "InboundMessage",
    "SentimentAnalysis",
]
