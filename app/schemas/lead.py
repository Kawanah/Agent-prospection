"""
Schémas Pydantic pour les Leads.
Utilisés pour la validation des données d'entrée/sortie de l'API.
"""

from datetime import datetime, date
from typing import Optional
from pydantic import BaseModel, Field, HttpUrl, field_validator

from app.models.lead import LeadStatus, LeadType, WebsiteMatchStatus


class LeadImportRow(BaseModel):
    """
    Schéma pour une ligne d'import depuis un fichier Excel/CSV.
    Adapté au format du fichier hebergements_classes.xlsx
    """

    # Colonnes du fichier source
    date_classement: Optional[str] = Field(None, alias="DATE DE CLASSEMENT")
    typologie: Optional[str] = Field(None, alias="TYPOLOGIE ÉTABLISSEMENT")
    classement: Optional[str] = Field(None, alias="CLASSEMENT")
    categorie: Optional[str] = Field(None, alias="CATÉGORIE")
    nom_commercial: str = Field(..., alias="NOM COMMERCIAL")
    adresse: Optional[str] = Field(None, alias="ADRESSE")
    code_postal: Optional[str] = Field(None, alias="CODE POSTAL")
    commune: Optional[str] = Field(None, alias="COMMUNE")
    site_internet: Optional[str] = Field(None, alias="SITE INTERNET")
    type_sejour: Optional[str] = Field(None, alias="TYPE DE SÉJOUR")
    capacite_accueil: Optional[int] = Field(
        None, alias="CAPACITÉ D'ACCUEIL (PERSONNES)"
    )
    nombre_chambres: Optional[int] = Field(None, alias="NOMBRE DE CHAMBRES")
    nombre_emplacements: Optional[int] = Field(None, alias="NOMBRE D'EMPLACEMENTS")

    class Config:
        populate_by_name = True  # Permet d'utiliser les alias

    @field_validator("code_postal", mode="before")
    @classmethod
    def clean_code_postal(cls, v):
        """Nettoie le code postal (convertit en string, enlève les décimales)."""
        if v is None:
            return None
        # Convertir en string et nettoyer
        v_str = str(v).strip()
        # Gérer les codes postaux qui arrivent comme des floats (75010.0 -> 75010)
        if "." in v_str:
            v_str = v_str.split(".")[0]
        # Ajouter un zéro devant si nécessaire (01000 -> 01000)
        if len(v_str) == 4:
            v_str = "0" + v_str
        return v_str

    @field_validator(
        "capacite_accueil", "nombre_chambres", "nombre_emplacements", mode="before"
    )
    @classmethod
    def clean_numbers(cls, v):
        """Nettoie les nombres (gère les valeurs vides et les strings)."""
        if v is None or v == "" or v == "-":
            return None
        try:
            return int(float(v))
        except (ValueError, TypeError):
            return None

    def to_lead_type(self) -> LeadType:
        """Convertit la typologie en LeadType."""
        if not self.typologie:
            return LeadType.OTHER
        typologie_lower = self.typologie.lower()
        if "hôtel" in typologie_lower or "hotel" in typologie_lower:
            return LeadType.HOTEL
        elif "camping" in typologie_lower:
            return LeadType.CAMPING
        elif "résidence" in typologie_lower or "residence" in typologie_lower:
            return LeadType.RESIDENCE
        elif (
            "meublé" in typologie_lower
            or "gîte" in typologie_lower
            or "gite" in typologie_lower
        ):
            return LeadType.GITE
        elif "chambre" in typologie_lower:
            return LeadType.CHAMBRE_HOTES
        else:
            return LeadType.OTHER


class LeadCreate(BaseModel):
    """Schéma pour créer un Lead via l'API."""

    name: str
    lead_type: LeadType = LeadType.OTHER
    address: Optional[str] = None
    city: Optional[str] = None
    postal_code: Optional[str] = None
    region: Optional[str] = None
    country: str = "France"
    website: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None


class LeadResponse(BaseModel):
    """Schéma pour retourner un Lead depuis l'API."""

    id: int
    name: str
    lead_type: LeadType
    city: Optional[str] = None
    postal_code: Optional[str] = None
    region: Optional[str] = None
    address: Optional[str] = None
    website: Optional[str] = None
    has_website: Optional[bool] = None
    website_match_status: WebsiteMatchStatus = WebsiteMatchStatus.UNKNOWN
    website_match_confidence: Optional[int] = None
    website_match_source: Optional[str] = None
    website_match_reasons: Optional[dict] = None
    website_review_checklist: Optional[dict] = None
    website_validated_at: Optional[datetime] = None
    website_quality_score: Optional[int] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    score: int
    seo_score: Optional[int] = None
    geo_score: Optional[int] = None
    star_rating: Optional[str] = None
    room_count: Optional[int] = None
    capacity: Optional[int] = None
    is_mobile_friendly: Optional[bool] = None
    has_booking_system: Optional[bool] = None
    booking_platform: Optional[str] = None
    google_rating: Optional[float] = None
    google_reviews_count: Optional[int] = None
    google_reviews_frequency: Optional[float] = None
    google_reviews_trend: Optional[str] = None
    established_date: Optional[date] = None
    status: LeadStatus
    source: Optional[str] = None
    notes: Optional[str] = None
    enriched_at: Optional[datetime] = None
    created_at: datetime

    # Nouvelles Entreprises (RCS/BODACC)
    is_nouvelle_entreprise: bool = False
    siren: Optional[str] = None
    objet_social: Optional[str] = None
    capital: Optional[int] = None
    forme_juridique: Optional[str] = None
    domiciliation: Optional[str] = None
    is_domiciliataire: Optional[bool] = None
    bodacc_activite: Optional[str] = None
    bodacc_publication_date: Optional[date] = None
    rcs_score: Optional[int] = None

    class Config:
        from_attributes = True


class LeadListResponse(BaseModel):
    """Réponse paginée pour la liste des leads."""

    total: int
    page: int
    per_page: int
    leads: list[LeadResponse]


class ImportResult(BaseModel):
    """Résultat d'un import de fichier."""

    success: bool
    total_rows: int
    imported: int
    skipped: int
    errors: int
    error_details: list[str] = []
