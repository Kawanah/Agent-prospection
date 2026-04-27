"""
Schémas Pydantic pour les Contacts.
Utilisés pour la validation des données d'entrée/sortie de l'API.
"""

from datetime import datetime, date
from typing import Optional
from pydantic import BaseModel, EmailStr, Field

from app.models.contact import ContactRole


class ContactCreate(BaseModel):
    """Schéma pour créer un Contact via l'API."""

    lead_id: int
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    full_name: Optional[str] = None
    role: ContactRole = ContactRole.OTHER
    job_title: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    mobile: Optional[str] = None
    linkedin_url: Optional[str] = None
    source: Optional[str] = None
    notes: Optional[str] = None


class ContactUpdate(BaseModel):
    """Schéma pour mettre à jour un Contact."""

    first_name: Optional[str] = None
    last_name: Optional[str] = None
    full_name: Optional[str] = None
    role: Optional[ContactRole] = None
    job_title: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    mobile: Optional[str] = None
    linkedin_url: Optional[str] = None
    linkedin_connected: Optional[bool] = None
    email_verified: Optional[bool] = None
    email_confidence: Optional[int] = None
    notes: Optional[str] = None


class ContactResponse(BaseModel):
    """Schéma pour retourner un Contact depuis l'API."""

    id: int
    lead_id: int
    first_name: Optional[str]
    last_name: Optional[str]
    full_name: Optional[str]
    role: ContactRole
    job_title: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    mobile: Optional[str]
    linkedin_url: Optional[str]
    date_naissance: Optional[date] = None
    linkedin_connected: bool
    email_verified: bool
    email_confidence: Optional[int]
    source: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class ContactListResponse(BaseModel):
    """Réponse paginée pour la liste des contacts."""

    total: int
    page: int
    per_page: int
    contacts: list[ContactResponse]
