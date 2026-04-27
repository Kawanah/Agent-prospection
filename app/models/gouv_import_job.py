"""
Modèle GouvImportJob — Suivi des imports depuis data.gouv.fr.
Chaque job représente une session d'import avec son checkpoint de reprise.
"""

import json
from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import String, Integer, DateTime, Text, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class JobStatus(str, Enum):
    """Statut d'un job d'import."""

    PENDING = "pending"  # Créé, pas encore lancé
    RUNNING = "running"  # En cours d'exécution
    PAUSED = "paused"  # Mis en pause manuellement
    COMPLETED = "completed"  # Terminé avec succès
    FAILED = "failed"  # Erreur fatale, arrêt


class GouvImportJob(Base):
    """
    Tracker d'un import data.gouv.fr.

    Le mécanisme de checkpoint fonctionne ainsi :
    - current_page : la page qu'on doit traiter au prochain démarrage/reprise
    - Après chaque lot de 100, on incrémente current_page et on commit
    - En cas d'interruption, on reprend depuis current_page
    """

    __tablename__ = "gouv_import_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)

    # ─── Paramètres du job (immuables une fois créé) ─────────────────────────
    dataset_slug: Mapped[str] = mapped_column(String(200))
    resource_id: Mapped[Optional[str]] = mapped_column(
        String(200)
    )  # ID ressource CSV sur data.gouv.fr
    lead_types_json: Mapped[Optional[str]] = mapped_column(
        Text
    )  # JSON: ["hotel", "camping"]
    region_filter: Mapped[Optional[str]] = mapped_column(String(100))
    department_filter: Mapped[Optional[str]] = mapped_column(
        String(10)
    )  # ex: "06", "75"
    star_filter: Mapped[Optional[str]] = mapped_column(
        Text
    )  # JSON: ["1", "2", "3"] ou null = tous
    batch_size: Mapped[int] = mapped_column(Integer, default=100)

    # ─── Checkpoint ─────────────────────────────────────────────────────────
    status: Mapped[JobStatus] = mapped_column(
        SQLEnum(JobStatus), default=JobStatus.PENDING, index=True
    )
    current_page: Mapped[int] = mapped_column(
        Integer, default=1
    )  # Page à traiter au prochain run
    total_pages: Mapped[Optional[int]] = mapped_column(
        Integer
    )  # Estimé depuis le total connu
    total_records_estimated: Mapped[Optional[int]] = mapped_column(Integer)

    # ─── Compteurs (mis à jour après chaque lot) ─────────────────────────────
    total_fetched: Mapped[int] = mapped_column(Integer, default=0)
    total_created: Mapped[int] = mapped_column(Integer, default=0)
    total_skipped: Mapped[int] = mapped_column(Integer, default=0)
    total_errors: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[Optional[str]] = mapped_column(Text)

    # ─── Timestamps ──────────────────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    last_checkpoint_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # ─── Helpers ─────────────────────────────────────────────────────────────

    @property
    def lead_types(self) -> list[str]:
        """Retourne la liste des types de leads à importer."""
        if not self.lead_types_json:
            return []
        return json.loads(self.lead_types_json)

    @lead_types.setter
    def lead_types(self, types: list[str]) -> None:
        self.lead_types_json = json.dumps(types)

    @property
    def progress_pct(self) -> Optional[float]:
        """Pourcentage d'avancement (0-100)."""
        if not self.total_pages or self.total_pages == 0:
            return None
        return round((self.current_page - 1) / self.total_pages * 100, 1)

    @property
    def can_resume(self) -> bool:
        """True si le job peut être relancé/repris."""
        return self.status in (JobStatus.PAUSED, JobStatus.RUNNING, JobStatus.FAILED)

    def __repr__(self) -> str:
        return (
            f"<GouvImportJob #{self.id} "
            f"dataset={self.dataset_slug} "
            f"status={self.status} "
            f"page={self.current_page}/{self.total_pages}>"
        )
