"""
Modèle Contact - Représente une personne décisionnaire dans un établissement.
"""

from datetime import datetime, date
from enum import Enum
from typing import Optional

from sqlalchemy import (
    String,
    Integer,
    DateTime,
    Date,
    Text,
    ForeignKey,
    Enum as SQLEnum,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ContactRole(str, Enum):
    """Rôle du contact dans l'établissement."""

    OWNER = "owner"  # Propriétaire
    DIRECTOR = "director"  # Directeur/Gérant
    MANAGER = "manager"  # Responsable
    MARKETING = "marketing"  # Responsable marketing/communication
    IT = "it"  # Responsable informatique/digital
    OTHER = "other"


class Contact(Base):
    """
    Un contact représente une personne dans un établissement.
    C'est la cible directe des messages de prospection.
    """

    __tablename__ = "contacts"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Lien vers l'établissement
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id"), index=True)

    # Identité
    first_name: Mapped[Optional[str]] = mapped_column(String(100))
    last_name: Mapped[Optional[str]] = mapped_column(String(100))
    full_name: Mapped[Optional[str]] = mapped_column(String(200))
    role: Mapped[ContactRole] = mapped_column(
        SQLEnum(ContactRole), default=ContactRole.OTHER
    )
    job_title: Mapped[Optional[str]] = mapped_column(String(200))

    # Coordonnées
    email: Mapped[Optional[str]] = mapped_column(String(255), index=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50))
    mobile: Mapped[Optional[str]] = mapped_column(String(50))

    # Date de naissance (dirigeant — depuis Pappers/BODACC)
    date_naissance: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    # LinkedIn
    linkedin_url: Mapped[Optional[str]] = mapped_column(String(500))
    linkedin_connected: Mapped[bool] = mapped_column(default=False)

    # Qualité des données
    email_verified: Mapped[bool] = mapped_column(default=False)
    email_confidence: Mapped[Optional[int]] = mapped_column(Integer)  # 0-100

    # Métadonnées
    source: Mapped[Optional[str]] = mapped_column(
        String(100)
    )  # Ex: "hunter", "linkedin", "website"
    notes: Mapped[Optional[str]] = mapped_column(Text)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relations
    lead: Mapped["Lead"] = relationship("Lead", back_populates="contacts")
    messages: Mapped[list["Message"]] = relationship(
        "Message", back_populates="contact"
    )

    @property
    def display_name(self) -> str:
        """Nom d'affichage du contact."""
        if self.full_name:
            return self.full_name
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.first_name or self.last_name or "Contact inconnu"

    def __repr__(self) -> str:
        return f"<Contact {self.id}: {self.display_name} ({self.role.value})>"
