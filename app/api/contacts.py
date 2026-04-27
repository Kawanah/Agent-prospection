"""
API endpoints pour la gestion des Contacts.
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from loguru import logger

from app.database import get_db
from app.models.contact import Contact, ContactRole
from app.models.lead import Lead
from app.schemas.contact import (
    ContactCreate,
    ContactUpdate,
    ContactResponse,
    ContactListResponse,
)

router = APIRouter()


@router.get("/", response_model=ContactListResponse)
async def list_contacts(
    page: int = Query(1, ge=1, description="Numéro de page"),
    per_page: int = Query(20, ge=1, le=100, description="Contacts par page"),
    lead_id: Optional[int] = Query(None, description="Filtrer par lead"),
    role: Optional[ContactRole] = Query(None, description="Filtrer par rôle"),
    email_verified: Optional[bool] = Query(None, description="Email vérifié ?"),
    db: AsyncSession = Depends(get_db),
):
    """
    Liste les contacts avec pagination et filtres.
    """
    query = select(Contact)

    if lead_id:
        query = query.where(Contact.lead_id == lead_id)
    if role:
        query = query.where(Contact.role == role)
    if email_verified is not None:
        query = query.where(Contact.email_verified == email_verified)

    # Compter le total
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # Pagination
    offset = (page - 1) * per_page
    query = query.order_by(Contact.created_at.desc()).offset(offset).limit(per_page)

    result = await db.execute(query)
    contacts = result.scalars().all()

    return ContactListResponse(
        total=total,
        page=page,
        per_page=per_page,
        contacts=[ContactResponse.model_validate(c) for c in contacts],
    )


@router.get("/{contact_id}", response_model=ContactResponse)
async def get_contact(contact_id: int, db: AsyncSession = Depends(get_db)):
    """
    Récupère un contact par son ID.
    """
    result = await db.execute(select(Contact).where(Contact.id == contact_id))
    contact = result.scalar_one_or_none()

    if not contact:
        raise HTTPException(status_code=404, detail="Contact non trouvé")

    return ContactResponse.model_validate(contact)


@router.post("/", response_model=ContactResponse, status_code=201)
async def create_contact(
    contact_data: ContactCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Crée un nouveau contact pour un lead.
    """
    # Vérifier que le lead existe
    lead_result = await db.execute(select(Lead).where(Lead.id == contact_data.lead_id))
    lead = lead_result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead non trouvé")

    contact = Contact(**contact_data.model_dump())
    db.add(contact)
    await db.commit()
    await db.refresh(contact)

    logger.info(f"Contact créé: {contact.display_name} pour {lead.name}")
    return ContactResponse.model_validate(contact)


@router.patch("/{contact_id}", response_model=ContactResponse)
async def update_contact(
    contact_id: int,
    contact_data: ContactUpdate,
    db: AsyncSession = Depends(get_db),
):
    """
    Met à jour un contact.
    """
    result = await db.execute(select(Contact).where(Contact.id == contact_id))
    contact = result.scalar_one_or_none()

    if not contact:
        raise HTTPException(status_code=404, detail="Contact non trouvé")

    # Mise à jour des champs fournis
    update_data = contact_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(contact, field, value)

    await db.commit()
    await db.refresh(contact)

    return ContactResponse.model_validate(contact)


@router.delete("/{contact_id}")
async def delete_contact(contact_id: int, db: AsyncSession = Depends(get_db)):
    """
    Supprime un contact.
    """
    result = await db.execute(select(Contact).where(Contact.id == contact_id))
    contact = result.scalar_one_or_none()

    if not contact:
        raise HTTPException(status_code=404, detail="Contact non trouvé")

    await db.delete(contact)
    await db.commit()

    return {"message": f"Contact {contact_id} supprimé"}


@router.get("/by-lead/{lead_id}", response_model=list[ContactResponse])
async def get_contacts_by_lead(lead_id: int, db: AsyncSession = Depends(get_db)):
    """
    Récupère tous les contacts d'un lead.
    """
    # Vérifier que le lead existe
    lead_result = await db.execute(select(Lead).where(Lead.id == lead_id))
    if not lead_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Lead non trouvé")

    result = await db.execute(
        select(Contact).where(Contact.lead_id == lead_id).order_by(Contact.role)
    )
    contacts = result.scalars().all()

    return [ContactResponse.model_validate(c) for c in contacts]
