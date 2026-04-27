"""
Modèle Lead - Représente un établissement (hôtel, camping, etc.)
"""

from datetime import datetime, date
from enum import Enum
from typing import Optional

from sqlalchemy import (
    String,
    Integer,
    Float,
    DateTime,
    Date,
    Text,
    Index,
    Enum as SQLEnum,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class LeadStatus(str, Enum):
    """Statut du lead dans le pipeline."""

    NEW = "new"  # Nouveau, non traité
    ENRICHED = "enriched"  # Enrichi avec les contacts
    NO_EMAIL = (
        "no_email"  # Enrichi mais sans email — contact alternatif (tél, LinkedIn)
    )
    CONTACTED = "contacted"  # Premier contact envoyé
    RESPONDED = "responded"  # A répondu
    INTERESTED = "interested"  # Intéressé
    NOT_INTERESTED = "not_interested"  # Pas intéressé
    CONVERTED = "converted"  # Converti en client
    INVALID = "invalid"  # Données invalides


class LeadType(str, Enum):
    """Type d'établissement."""

    HOTEL = "hotel"
    CAMPING = "camping"
    GITE = "gite"
    CHAMBRE_HOTES = "chambre_hotes"
    RESIDENCE = "residence"
    ACTIVITE = "activite"  # Prestataire d'activités
    OTHER = "other"


class Lead(Base):
    """
    Un lead représente un établissement prospect.
    C'est l'entité principale importée depuis les CSV.
    """

    __tablename__ = "leads"
    __table_args__ = (Index("ix_leads_status_score", "status", "score"),)

    id: Mapped[int] = mapped_column(primary_key=True)

    # Informations de base (depuis CSV)
    name: Mapped[str] = mapped_column(String(255), index=True)
    lead_type: Mapped[LeadType] = mapped_column(
        SQLEnum(LeadType), default=LeadType.OTHER
    )

    # Taille de l'établissement (depuis CSV)
    capacity: Mapped[Optional[int]] = mapped_column(
        Integer
    )  # Capacité d'accueil en personnes
    room_count: Mapped[Optional[int]] = mapped_column(
        Integer
    )  # Nombre de chambres (hôtels)
    pitch_count: Mapped[Optional[int]] = mapped_column(
        Integer
    )  # Nombre d'emplacements (campings)
    star_rating: Mapped[Optional[str]] = mapped_column(
        String(20)
    )  # Classement (étoiles)

    # Localisation
    address: Mapped[Optional[str]] = mapped_column(String(500))
    city: Mapped[Optional[str]] = mapped_column(String(100), index=True)
    postal_code: Mapped[Optional[str]] = mapped_column(String(20))
    region: Mapped[Optional[str]] = mapped_column(String(100))
    country: Mapped[str] = mapped_column(String(100), default="France")

    # Informations enrichies
    website: Mapped[Optional[str]] = mapped_column(String(500))
    phone: Mapped[Optional[str]] = mapped_column(String(50))
    email: Mapped[Optional[str]] = mapped_column(String(255))

    # Réseaux sociaux
    linkedin_url: Mapped[Optional[str]] = mapped_column(String(500))
    facebook_url: Mapped[Optional[str]] = mapped_column(String(500))
    instagram_url: Mapped[Optional[str]] = mapped_column(String(500))

    # Analyse du site web existant
    has_website: Mapped[Optional[bool]] = mapped_column(default=None)
    website_quality_score: Mapped[Optional[int]] = mapped_column(Integer)  # 0-100
    has_booking_system: Mapped[Optional[bool]] = mapped_column(default=None)
    booking_platform: Mapped[Optional[str]] = mapped_column(
        String(200)
    )  # Ex: "Amenitiz", "D-EDGE, Reservit"
    is_mobile_friendly: Mapped[Optional[bool]] = mapped_column(default=None)
    seo_score: Mapped[Optional[int]] = mapped_column(Integer)  # 0-100
    geo_score: Mapped[Optional[int]] = mapped_column(
        Integer
    )  # 0-100 (Generative Engine Optimization)

    # Analyse SEO réelle — DataForSEO (métriques Google organiques)
    dataforseo_domain_rank: Mapped[Optional[int]] = mapped_column(
        Integer
    )  # Autorité domaine 0-100
    dataforseo_organic_keywords: Mapped[Optional[int]] = mapped_column(
        Integer
    )  # Nb mots-clés positionnés
    dataforseo_organic_traffic: Mapped[Optional[int]] = mapped_column(
        Integer
    )  # Trafic organique estimé/mois
    dataforseo_analyzed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # Analyse des avis Google
    google_place_id: Mapped[Optional[str]] = mapped_column(
        String(255), index=True
    )  # ID Google Places
    google_rating: Mapped[Optional[float]] = mapped_column(
        Float
    )  # Note moyenne (1.0-5.0)
    google_reviews_count: Mapped[Optional[int]] = mapped_column(
        Integer
    )  # Nombre total d'avis
    google_reviews_period_months: Mapped[Optional[int]] = mapped_column(
        Integer
    )  # Période analysée en mois
    google_reviews_frequency: Mapped[Optional[float]] = mapped_column(
        Float
    )  # Avis par mois (moyenne)
    google_reviews_trend: Mapped[Optional[str]] = mapped_column(
        String(20)
    )  # "growing", "stable", "declining"
    google_reviews_analyzed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime
    )  # Dernière analyse

    # Scoring
    score: Mapped[int] = mapped_column(
        Integer, default=0, index=True
    )  # Score global 0-100

    # Statut et suivi
    status: Mapped[LeadStatus] = mapped_column(
        SQLEnum(LeadStatus), default=LeadStatus.NEW, index=True
    )

    # Métadonnées
    source: Mapped[Optional[str]] = mapped_column(
        String(100)
    )  # Ex: "csv_import", "data.gouv.fr"
    external_id: Mapped[Optional[str]] = mapped_column(
        String(200), index=True
    )  # ID officiel Atout France
    gouv_synced_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime
    )  # Dernière synchro data.gouv.fr
    established_date: Mapped[Optional[date]] = mapped_column(
        Date, nullable=True
    )  # Date création INSEE/SIRENE
    notes: Mapped[Optional[str]] = mapped_column(Text)

    # ── Nouvelles Entreprises (données RCS / BODACC) ──
    is_nouvelle_entreprise: Mapped[bool] = mapped_column(default=False, index=True)
    siren: Mapped[Optional[str]] = mapped_column(String(20), index=True)
    objet_social: Mapped[Optional[str]] = mapped_column(Text)
    capital: Mapped[Optional[int]] = mapped_column(Integer)
    forme_juridique: Mapped[Optional[str]] = mapped_column(String(50))
    domiciliation: Mapped[Optional[str]] = mapped_column(String(500))
    is_domiciliataire: Mapped[Optional[bool]] = mapped_column(default=None)
    bodacc_activite: Mapped[Optional[str]] = mapped_column(Text)
    bodacc_publication_date: Mapped[Optional[date]] = mapped_column(Date)
    rcs_score: Mapped[Optional[int]] = mapped_column(Integer)

    # Lot d'import
    batch_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    enriched_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    last_contacted_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # Relations
    contacts: Mapped[list["Contact"]] = relationship("Contact", back_populates="lead")
    messages: Mapped[list["Message"]] = relationship("Message", back_populates="lead")

    def calculate_score(self) -> int:
        """
        Calcule le score de priorité du lead (0-100).
        Plus le score est élevé, plus le prospect est prioritaire.

        Critères de scoring :
        - Pas de site web : +30 pts (besoin évident)
        - Site web de mauvaise qualité : +40 pts (priorité #1)
        - Site non mobile-friendly : +15 pts
        - Mauvais SEO (< 40) : +20 pts
        - Mauvais GEO (< 40) : +15 pts (pas optimisé pour les IA)
        - Type hôtel : +15 pts (cible préférée)
        - Taille établissement : +5 à +15 pts (plus gros = plus de budget)
        - Pas de réservation en ligne : +10 pts
        - Avis Google :
          - Beaucoup d'avis (popularité) : +5 à +10 pts
          - Fréquence élevée (récurrence) : +3 à +8 pts
          - Tendance "growing" : +5 pts / "declining" : +8 pts
          - Note < 3.5 : +10 pts (besoin de réputation)
        """
        points = 0

        # 1. Présence et qualité du site web
        # IMPORTANT : on ne suppose jamais "pas de site" si has_website est inconnu (None).
        # L'absence d'URL dans data.gouv.fr ne signifie pas absence de site web réel.
        # Seul has_website=False (confirmé après enrichissement) déclenche les bonus.

        if self.has_website is False:
            if self.website is not None and self.website_quality_score is None:
                # URL connue mais site inaccessible/expiré
                points += 35
            else:
                # Enrichissement confirmé : pas de site
                points += 30

        # Site web de mauvaise qualité (confirmé après analyse)
        elif self.website_quality_score is not None:
            if self.website_quality_score < 40:
                points += 40  # Site moche/ancien = priorité maximale
            elif self.website_quality_score < 60:
                points += 20  # Site moyen
        # else : has_website=None (non enrichi) ou has_website=True avec bon site → 0 bonus

        # 3. Site non mobile-friendly → +15 points
        if self.is_mobile_friendly is False:
            points += 15

        # 4. Mauvais SEO (score < 40) → +20 points
        if self.seo_score is not None:
            if self.seo_score < 40:
                points += 20
            elif self.seo_score < 60:
                points += 10

        # 5. Mauvais GEO (score < 40) → +15 points (pas optimisé pour les moteurs IA)
        if self.geo_score is not None:
            if self.geo_score < 40:
                points += 15  # Pas de données structurées, pas de FAQ = opportunité GEO
            elif self.geo_score < 60:
                points += 8

        # 6. Type d'établissement (hôtels prioritaires)
        if self.lead_type == LeadType.HOTEL:
            points += 15  # Hôtels = cible préférée
        elif self.lead_type in (LeadType.CAMPING, LeadType.RESIDENCE):
            points += 10
        elif self.lead_type in (LeadType.GITE, LeadType.CHAMBRE_HOTES):
            points += 8
        elif self.lead_type == LeadType.ACTIVITE:
            points += 5

        # 7. Taille de l'établissement (plus gros = plus de budget potentiel)
        size_score = 0

        # Pour les hôtels/résidences : nombre de chambres
        if self.room_count is not None:
            if self.room_count >= 100:
                size_score = 15  # Grand hôtel
            elif self.room_count >= 50:
                size_score = 12
            elif self.room_count >= 20:
                size_score = 8
            elif self.room_count >= 10:
                size_score = 5

        # Pour les campings : nombre d'emplacements
        elif self.pitch_count is not None:
            if self.pitch_count >= 200:
                size_score = 15  # Grand camping
            elif self.pitch_count >= 100:
                size_score = 12
            elif self.pitch_count >= 50:
                size_score = 8
            elif self.pitch_count >= 20:
                size_score = 5

        # Fallback sur la capacité d'accueil
        elif self.capacity is not None:
            if self.capacity >= 200:
                size_score = 12
            elif self.capacity >= 100:
                size_score = 8
            elif self.capacity >= 50:
                size_score = 5

        points += size_score

        # 8. DataForSEO — Présence SEO réelle sur Google
        if self.dataforseo_organic_keywords is not None:
            if self.dataforseo_organic_keywords == 0:
                points += 20  # Site invisible sur Google = opportunité maximale
            elif self.dataforseo_organic_keywords < 10:
                points += 12  # Très faible présence SEO
            elif self.dataforseo_organic_keywords < 50:
                points += 6  # Présence modeste

        if self.dataforseo_organic_traffic is not None:
            if self.dataforseo_organic_traffic == 0:
                points += 10  # Aucun trafic organique
            elif self.dataforseo_organic_traffic < 100:
                points += 5  # Trafic très faible

        # 10. Avis Google - Indicateurs de qualité et d'activité
        if self.google_reviews_count is not None:
            # Établissement populaire (beaucoup d'avis) = actif et visible
            if self.google_reviews_count >= 100:
                points += 10  # Très populaire
            elif self.google_reviews_count >= 50:
                points += 7
            elif self.google_reviews_count >= 20:
                points += 5

            # Fréquence des avis (récurrence) - indicateur d'activité
            if self.google_reviews_frequency is not None:
                if self.google_reviews_frequency >= 5:  # 5+ avis/mois = très actif
                    points += 8
                elif self.google_reviews_frequency >= 2:  # 2-5 avis/mois = actif
                    points += 5
                elif self.google_reviews_frequency < 0.5:  # < 0.5 avis/mois = peu actif
                    points += 3  # Opportunité : besoin de visibilité

            # Tendance des avis
            if self.google_reviews_trend == "growing":
                points += 5  # Établissement en croissance = budget potentiel
            elif self.google_reviews_trend == "declining":
                points += 8  # En déclin = besoin d'aide urgente

        # Note Google - Indicateur de réputation
        if self.google_rating is not None:
            if self.google_rating < 3.5:
                points += 10  # Mauvaise réputation = besoin de gestion de réputation
            elif self.google_rating >= 4.5:
                points += (
                    3  # Excellente réputation = argument de vente pour site premium
                )

        # Plafonner à 100
        return min(points, 100)

    def update_score(self) -> None:
        """Met à jour le score du lead."""
        self.score = self.calculate_score()

    def calculate_rcs_score(self) -> int:
        """
        Score spécifique aux nouvelles entreprises (0-5 pts).
        Séparé du score hospitalité (0-100).

        Critères :
        - Inscrite au RCS (+2) : entreprise sérieuse
        - Capital > 1 000 € (+1) : a un budget
        - SAS / SASU (pas EI) (+1) : structure formelle
        - Pas de site web détecté (+1) : besoin immédiat
        """
        if not self.is_nouvelle_entreprise:
            return 0
        points = 0
        if self.siren or self.external_id:
            points += 2
        if self.capital and self.capital > 1000:
            points += 1
        if self.forme_juridique and self.forme_juridique.upper() in (
            "SAS",
            "SASU",
            "SARL",
            "SA",
            "EURL",
        ):
            points += 1
        # +1 seulement si l'enrichissement a CONFIRMÉ l'absence de site
        # has_website=None = inconnu (pas encore enrichi) → pas de point
        if self.has_website is False:
            points += 1
        return min(points, 5)

    def update_rcs_score(self) -> None:
        """Met à jour le score RCS."""
        self.rcs_score = self.calculate_rcs_score()

    @property
    def has_valid_website_url(self) -> bool:
        """Vérifie si l'URL du site web est valide (pas vide, pas '-', etc.)."""
        if not self.website:
            return False
        invalid_urls = ["-", "n/a", "na", "none", "null", ""]
        return (
            self.website.strip().lower() not in invalid_urls
            and len(self.website.strip()) > 3
        )

    @property
    def priority_level(self) -> str:
        """Retourne le niveau de priorité en texte."""
        # Pas de site web du tout = CHAUD (meilleur prospect !)
        if not self.has_valid_website_url:
            return "🔥 SANS SITE"

        # Site inaccessible (URL valide mais analyse échouée) = À VÉRIFIER
        if self.website_quality_score is None and self.has_website is False:
            return "⚠️ À VÉRIFIER"

        if self.score >= 80:
            return "🔥 CHAUD"
        elif self.score >= 50:
            return "😐 TIÈDE"
        else:
            return "❄️ FROID"

    def __repr__(self) -> str:
        return f"<Lead {self.id}: {self.name} ({self.status.value})>"
