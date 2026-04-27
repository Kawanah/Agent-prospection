"""
Modèles SQLAlchemy pour l'Agent de Prospection.
"""

from app.models.lead import Lead, LeadStatus, LeadType
from app.models.contact import Contact, ContactRole
from app.models.campaign import Campaign, CampaignStatus, CampaignChannel
from app.models.message import (
    Message,
    MessageChannel,
    MessageDirection,
    MessageStatus,
    SentimentType,
)
from app.models.gouv_import_job import GouvImportJob, JobStatus
from app.models.import_batch import ImportBatch

__all__ = [
    # Lead
    "Lead",
    "LeadStatus",
    "LeadType",
    # Contact
    "Contact",
    "ContactRole",
    # Campaign
    "Campaign",
    "CampaignStatus",
    "CampaignChannel",
    # Message
    "Message",
    "MessageChannel",
    "MessageDirection",
    "MessageStatus",
    "SentimentType",
    # Import data.gouv.fr
    "GouvImportJob",
    "JobStatus",
    # Lots d'import
    "ImportBatch",
]
