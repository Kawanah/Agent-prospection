"""
API endpoints pour la génération de messages IA.
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.lead import Lead
from app.services.ai_service import (
    AIService,
    MessageChannel,
    MessageTone,
    generate_message_for_lead,
)

router = APIRouter()


_PROMPT_INJECTION_PATTERNS = [
    "ignore previous",
    "ignore all previous",
    "system:",
    "assistant:",
    "<|",
    "|>",
    "forget your instructions",
    "new instructions",
    "act as",
]


class MessageRequest(BaseModel):
    """Requête pour générer un message."""

    channel: str = "email"  # email ou linkedin
    tone: str = "friendly"  # professional, friendly, direct
    sender_name: str = "L'équipe Kawanah Travel"
    custom_instructions: Optional[str] = None

    @field_validator("custom_instructions")
    @classmethod
    def sanitize_custom_instructions(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        if len(v) > 500:
            raise ValueError("custom_instructions ne peut pas dépasser 500 caractères")
        v_lower = v.lower()
        for pattern in _PROMPT_INJECTION_PATTERNS:
            if pattern in v_lower:
                raise ValueError("Instructions personnalisées invalides")
        return v


class MessageResponse(BaseModel):
    """Réponse avec le message généré."""

    lead_id: int
    lead_name: str
    lead_segment: str
    subject: str
    body: str
    channel: str
    tone: str
    personalization_points: list[str]


@router.post("/generate/{lead_id}", response_model=MessageResponse)
async def generate_message(
    lead_id: int,
    request: MessageRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Génère un message personnalisé pour un lead.

    Le message est adapté selon :
    - Le segment du lead (SANS SITE, À VÉRIFIER, CHAUD, TIÈDE, FROID)
    - Les scores d'analyse (SEO, GEO, qualité)
    - Le canal choisi (email, LinkedIn)
    - Le ton demandé (professionnel, amical, direct)
    """
    # Récupérer le lead
    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()

    if not lead:
        raise HTTPException(status_code=404, detail="Lead non trouvé")

    # Valider les paramètres
    try:
        channel = MessageChannel(request.channel)
        tone = MessageTone(request.tone)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Canal ou ton invalide. Canaux: email, linkedin. Tons: professional, friendly, direct",
        )

    # Générer le message
    service = AIService()
    message = service.generate_message(
        lead=lead,
        channel=channel,
        tone=tone,
        sender_name=request.sender_name,
        custom_instructions=request.custom_instructions,
    )

    return MessageResponse(
        lead_id=lead.id,
        lead_name=lead.name,
        lead_segment=lead.priority_level,
        subject=message.subject,
        body=message.body,
        channel=message.channel.value,
        tone=message.tone.value,
        personalization_points=message.personalization_points,
    )


@router.post("/generate/batch")
async def generate_messages_batch(
    request: MessageRequest,
    segment: Optional[str] = Query(
        default=None,
        description="Filtrer par segment: 'sans_site', 'a_verifier', 'chaud', 'tiede', 'froid'",
    ),
    limit: int = Query(default=5, le=20),
    db: AsyncSession = Depends(get_db),
):
    """
    Génère des messages pour plusieurs leads d'un segment.
    Utile pour préparer une campagne.
    """
    query = select(Lead)

    # Filtrer par segment
    if segment:
        segment_lower = segment.lower()
        if segment_lower == "sans_site":
            # Leads sans site valide
            query = query.where(Lead.website.is_(None) | (Lead.website == "-"))
        elif segment_lower == "a_verifier":
            # Sites inaccessibles
            query = query.where(
                Lead.website.isnot(None),
                Lead.has_website == False,
                Lead.website_quality_score.is_(None),
            )
        elif segment_lower == "chaud":
            query = query.where(Lead.score >= 80)
        elif segment_lower == "tiede":
            query = query.where(Lead.score >= 50, Lead.score < 80)
        elif segment_lower == "froid":
            query = query.where(Lead.score < 50)

    query = query.limit(limit)

    result = await db.execute(query)
    leads = result.scalars().all()

    # Générer les messages
    service = AIService()
    try:
        channel = MessageChannel(request.channel)
        tone = MessageTone(request.tone)
    except ValueError:
        raise HTTPException(status_code=400, detail="Canal ou ton invalide")

    messages = []
    for lead in leads:
        message = service.generate_message(
            lead=lead,
            channel=channel,
            tone=tone,
            sender_name=request.sender_name,
        )
        messages.append(
            {
                "lead_id": lead.id,
                "lead_name": lead.name,
                "lead_segment": lead.priority_level,
                "subject": message.subject,
                "body": message.body,
            }
        )

    return {
        "total": len(messages),
        "segment": segment,
        "channel": request.channel,
        "tone": request.tone,
        "messages": messages,
    }


@router.post("/variations/{lead_id}")
async def generate_variations(
    lead_id: int,
    count: int = Query(default=3, le=3, description="Nombre de variations (max 3)"),
    channel: str = Query(default="email"),
    db: AsyncSession = Depends(get_db),
):
    """
    Génère plusieurs variations d'un message pour A/B testing.
    Chaque variation a un ton différent (professionnel, amical, direct).
    """
    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()

    if not lead:
        raise HTTPException(status_code=404, detail="Lead non trouvé")

    service = AIService()

    try:
        channel_enum = MessageChannel(channel)
    except ValueError:
        raise HTTPException(status_code=400, detail="Canal invalide")

    variations = service.generate_variations(
        lead=lead,
        count=count,
        channel=channel_enum,
    )

    return {
        "lead_id": lead.id,
        "lead_name": lead.name,
        "lead_segment": lead.priority_level,
        "variations": [
            {
                "tone": v.tone.value,
                "subject": v.subject,
                "body": v.body,
            }
            for v in variations
        ],
    }


@router.get("/templates")
async def get_templates():
    """
    Retourne les templates de stratégie par segment.
    Utile pour comprendre l'approche de chaque type de message.
    """
    from app.services.ai_service import MessageTemplates

    return {
        "segments": {
            "sans_site": {
                "description": "Établissement sans site web",
                "strategy": MessageTemplates.SANS_SITE.strip(),
                "recommended_tone": "friendly",
            },
            "a_verifier": {
                "description": "Site web inaccessible",
                "strategy": MessageTemplates.A_VERIFIER.strip(),
                "recommended_tone": "friendly",
            },
            "chaud": {
                "description": "Site de mauvaise qualité",
                "strategy": MessageTemplates.CHAUD.strip(),
                "recommended_tone": "professional",
            },
            "tiede": {
                "description": "Site correct mais améliorable",
                "strategy": MessageTemplates.TIEDE_GEO.strip(),
                "recommended_tone": "friendly",
            },
            "froid": {
                "description": "Bon site, opportunité GEO",
                "strategy": MessageTemplates.FROID_GEO.strip(),
                "recommended_tone": "professional",
            },
        },
        "channels": ["email", "linkedin"],
        "tones": ["professional", "friendly", "direct"],
    }
