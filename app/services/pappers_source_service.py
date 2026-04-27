"""
Source Pappers — Import via l'API Pappers.fr

Avantages vs Sirene :
- Données enrichies : dirigeants inclus dans la réponse principale
- Site web directement disponible (si renseigné)
- Filtre par date de création → détecte les nouvelles structures
- Filtre "actif uniquement" natif
- Accès gratuit pendant 15 jours (puis payant)

Use case principal :
    Trouver des nouvelles structures hospitalité (< 6 mois)
    qui n'ont probablement pas encore de site web → prospect chaud idéal

Codes NAF hospitalité :
    5510Z — Hôtels et hébergements similaires
    5520Z — Hébergements touristiques de courte durée (gîtes, B&B…)
    5530Z — Terrains de camping
    7990Z — Services de réservation et activités connexes
    9329Z — Autres activités récréatives et de loisirs
    9319Z — Autres activités sportives (outdoor)

Doc API : https://www.pappers.fr/api/documentation
"""

from datetime import datetime, date, timedelta
from typing import Optional

import httpx
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.lead import Lead, LeadStatus, LeadType

settings = get_settings()

# ─── Configuration API ────────────────────────────────────────────────────────
PAPPERS_API = "https://api.pappers.fr/v2"

# ─── Codes NAF disponibles pour l'import ──────────────────────────────────────
NAF_CODES_PAPPERS = {
    "5510Z": {
        "label": "Hôtels et hébergements similaires",
        "lead_type": LeadType.HOTEL,
    },
    "5520Z": {
        "label": "Hébergements touristiques de courte durée (gîtes, B&B)",
        "lead_type": LeadType.GITE,
    },
    "5530Z": {
        "label": "Terrains de camping et parcs pour caravanes",
        "lead_type": LeadType.CAMPING,
    },
    "7990Z": {
        "label": "Autres services de réservation et activités connexes",
        "lead_type": LeadType.ACTIVITE,
    },
    "9329Z": {
        "label": "Autres activités récréatives et de loisirs",
        "lead_type": LeadType.ACTIVITE,
    },
    "9319Z": {
        "label": "Autres activités sportives (outdoor, guides)",
        "lead_type": LeadType.ACTIVITE,
    },
}


class PappersSourceService:
    """
    Import de leads depuis l'API Pappers.fr

    Usage :
        service = PappersSourceService()
        result = await service.search_and_import(
            db=db,
            naf_codes=["5510Z", "5520Z"],
            department="33",
            max_results=200,
            new_only=True,          # Nouvelles structures uniquement
            months_back=6,          # Créées dans les 6 derniers mois
        )
    """

    def __init__(self):
        self.api_key = settings.pappers_api_key
        self.client = httpx.AsyncClient(timeout=20.0)

    async def close(self):
        await self.client.aclose()

    async def _fetch_companies(
        self,
        naf_code: str,
        department: str,
        page: int = 1,
        per_page: int = 100,
        date_creation_min: Optional[str] = None,
    ) -> dict:
        """Appelle l'API Pappers pour récupérer des entreprises."""
        if not self.api_key:
            raise PermissionError(
                "PAPPERS_API_KEY non configurée. "
                "Ajoutez votre clé dans le fichier .env"
            )

        params = {
            "api_token": self.api_key,
            "code_naf": naf_code,
            "departement": department,
            "entreprise_cessee": "false",  # Actifs uniquement
            "page": page,
            "par_page": per_page,
        }

        if date_creation_min:
            params["date_creation_min"] = date_creation_min

        try:
            response = await self.client.get(
                f"{PAPPERS_API}/recherche",
                params=params,
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise PermissionError("Clé API Pappers invalide ou expirée")
            logger.error(f"Erreur API Pappers: {e}")
            raise

    async def search_and_import(
        self,
        db: AsyncSession,
        naf_codes: list[str],
        department: str,
        max_results: int = 200,
        new_only: bool = False,
        months_back: int = 6,
    ) -> dict:
        """
        Recherche et importe des entreprises depuis Pappers.

        Args:
            db: Session base de données
            naf_codes: Codes NAF à importer (ex: ["5510Z", "5520Z"])
            department: Code département (ex: "33")
            max_results: Nombre max de leads à importer
            new_only: Si True, importe uniquement les créées récemment
            months_back: Nombre de mois en arrière pour "new_only"
        """
        date_min = None
        if new_only:
            cutoff = date.today() - timedelta(days=months_back * 30)
            date_min = cutoff.strftime("%Y-%m-%d")
            logger.info(f"Filtre nouvelles structures depuis : {date_min}")

        imported = 0
        skipped = 0
        total_fetched = 0
        errors = []
        new_no_website = 0

        for naf_code in naf_codes:
            if imported >= max_results:
                break

            naf_info = NAF_CODES_PAPPERS.get(naf_code, {})
            lead_type = naf_info.get("lead_type", LeadType.OTHER)

            page = 1
            per_page = min(100, max_results - imported + 20)  # petite marge

            while imported < max_results:
                try:
                    data = await self._fetch_companies(
                        naf_code=naf_code,
                        department=department,
                        page=page,
                        per_page=per_page,
                        date_creation_min=date_min,
                    )
                except PermissionError:
                    raise
                except Exception as e:
                    errors.append(f"NAF {naf_code} page {page}: {str(e)}")
                    break

                results = data.get("resultats", [])
                if not results:
                    break

                total_fetched += len(results)

                for company in results:
                    if imported >= max_results:
                        break

                    lead, was_created, is_new_no_website = await self._create_lead(
                        db=db,
                        company=company,
                        lead_type=lead_type,
                        naf_code=naf_code,
                    )

                    if lead is None:
                        errors.append(
                            f"Erreur création lead: {company.get('nom_entreprise', '?')}"
                        )
                        continue

                    if was_created:
                        imported += 1
                        if is_new_no_website:
                            new_no_website += 1
                    else:
                        skipped += 1

                # Pagination
                total_api = data.get("total", 0)
                if page * per_page >= total_api:
                    break
                page += 1

        await db.commit()

        logger.info(
            f"Pappers import terminé — importés: {imported}, "
            f"doublons ignorés: {skipped}, "
            f"nouvelles structures sans site: {new_no_website}"
        )

        return {
            "imported": imported,
            "skipped": skipped,
            "total_fetched": total_fetched,
            "new_no_website": new_no_website,
            "errors": errors[:10],
        }

    async def _create_lead(
        self,
        db: AsyncSession,
        company: dict,
        lead_type: LeadType,
        naf_code: str,
    ) -> tuple[Optional[Lead], bool, bool]:
        """
        Crée un lead depuis les données Pappers.

        Returns:
            (lead, was_created, is_new_no_website)
        """
        siren = company.get("siren", "")
        name = company.get("nom_entreprise") or company.get("denomination", "")

        if not name:
            return None, False, False

        # ── Déduplication par SIREN (le plus fiable) ──
        if siren:
            existing = await db.execute(select(Lead).where(Lead.external_id == siren))
            if existing.scalar_one_or_none():
                return None, False, False

        # ── Déduplication par nom + ville ──
        siege = company.get("siege", {})
        city = siege.get("ville", "")

        existing = await db.execute(
            select(Lead).where(
                Lead.name == name,
                Lead.city == city,
            )
        )
        if existing.scalar_one_or_none():
            return None, False, False

        # ── Construire le lead ──
        address = siege.get("adresse_ligne_1", "")
        postal_code = siege.get("code_postal", "")
        website = company.get("site_internet") or None
        date_creation_str = company.get("date_creation")
        phone = company.get("telephone") or None

        # Dirigeant principal (Pappers renvoie déjà la liste)
        dirigeants = company.get("dirigeants", [])
        first_contact_name = None
        first_contact_role = None
        if dirigeants:
            d = dirigeants[0]
            prenom = d.get("prenom", "")
            nom = d.get("nom", "")
            qualite = d.get("qualite", "")
            if prenom or nom:
                first_contact_name = f"{prenom} {nom}".strip()
                first_contact_role = qualite

        # Détection "nouvelle structure sans site"
        is_new = False
        is_new_no_website = False
        if date_creation_str:
            try:
                creation_date = datetime.strptime(
                    date_creation_str[:10], "%Y-%m-%d"
                ).date()
                months_old = (date.today() - creation_date).days / 30
                is_new = months_old <= 12
                is_new_no_website = is_new and not website
            except (ValueError, TypeError):
                pass

        # Construire les notes avec toutes les infos utiles
        notes_parts = []
        if first_contact_name:
            notes_parts.append(
                f"Dirigeant: {first_contact_name} ({first_contact_role})"
                if first_contact_role
                else f"Dirigeant: {first_contact_name}"
            )
        if naf_code:
            notes_parts.append(f"NAF: {naf_code}")
        if is_new:
            notes_parts.append("⭐ Nouvelle structure")
        if is_new_no_website:
            notes_parts.append("🔥 Nouvelle sans site")

        lead = Lead(
            name=name,
            city=city,
            address=address,
            postal_code=postal_code,
            phone=phone,
            website=website,
            has_website=bool(website) if website else None,
            lead_type=lead_type,
            status=LeadStatus.NEW,
            source="pappers",
            external_id=siren,  # SIREN stocké dans external_id
            established_date=datetime.strptime(
                date_creation_str[:10], "%Y-%m-%d"
            ).date()
            if date_creation_str
            else None,
            notes=" | ".join(notes_parts) if notes_parts else None,
        )

        db.add(lead)
        return lead, True, is_new_no_website
