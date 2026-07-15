"""
Source Google Places — Import de leads via Google Maps Platform.

Couvre TOUS les types d'établissements (classés ou non) :
gîtes, chambres d'hôtes, B&B, activités, nouveaux établissements.

Endpoint : Places Text Search
https://developers.google.com/maps/documentation/places/web-service/text-search

Clé API requise : GOOGLE_PLACES_API_KEY dans .env
Prix indicatif : ~0,017 $ / requête (200 résultats = ~4 pages = ~0,07 $)
"""

import asyncio
from datetime import datetime
from typing import Optional

import httpx
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.import_batch import ImportBatch
from app.models.lead import Lead, LeadStatus, LeadType

# ─── URL de l'API Google Places ───────────────────────────────────────────────
PLACES_TEXT_SEARCH = "https://maps.googleapis.com/maps/api/place/textsearch/json"

# ─── Mapping type interne → requête Google Places ─────────────────────────────
QUERY_MAP: dict[str, str] = {
    "hotel": "hôtel tourisme",
    "camping": "camping",
    "gite": "gîte rural",
    "chambre_hotes": "chambre hôtes",
    "residence": "résidence tourisme",
    "activite": "activité outdoor loisirs",
    "other": "hébergement",
}

TYPE_MAP: dict[str, LeadType] = {
    "hotel": LeadType.HOTEL,
    "camping": LeadType.CAMPING,
    "gite": LeadType.GITE,
    "chambre_hotes": LeadType.CHAMBRE_HOTES,
    "residence": LeadType.RESIDENCE,
    "activite": LeadType.ACTIVITE,
    "other": LeadType.OTHER,
}


class GooglePlacesSourceService:
    """
    Import de leads depuis l'API Google Places Text Search.

    Usage :
        service = GooglePlacesSourceService()
        result = await service.search_and_import(
            db=db,
            lead_types=["hotel", "camping"],
            location="Bordeaux",
            radius_km=30,
            max_results=200,
        )
    """

    def __init__(self) -> None:
        self.api_key = get_settings().google_places_api_key

    async def search_and_import(
        self,
        db: AsyncSession,
        lead_types: list[str],
        location: str,
        radius_km: int = 30,
        max_results: int = 200,
    ) -> dict:
        """
        Recherche des établissements via Google Places et les crée en base.

        Params :
            lead_types  : liste de types ex. ["hotel", "camping"]
            location    : ville ou département ex. "Bordeaux", "Gironde"
            radius_km   : rayon de recherche en km (info uniquement pour la requête texte)
            max_results : plafond total de leads à importer
        """
        if not self.api_key:
            raise ValueError(
                "GOOGLE_PLACES_API_KEY non configurée dans .env. "
                "Obtenez une clé sur https://console.cloud.google.com/"
            )

        # Créer le lot d'import
        batch = ImportBatch(
            name=(
                f"Google Places — {location} — "
                f"{', '.join(lead_types)} — "
                f"{datetime.now().strftime('%d/%m/%Y %H:%M')}"
            ),
            source="google_places",
        )
        db.add(batch)
        await db.flush()

        total_created = 0
        total_skipped = 0
        warnings: list[str] = []
        quota_per_type = max(1, max_results // len(lead_types))

        async with httpx.AsyncClient(timeout=30) as client:
            for type_key in lead_types:
                query = f"{QUERY_MAP.get(type_key, type_key)} {location}"
                lead_type = TYPE_MAP.get(type_key, LeadType.OTHER)

                created, skipped, type_warnings = await self._import_type(
                    client=client,
                    db=db,
                    batch_id=batch.id,
                    query=query,
                    lead_type=lead_type,
                    max_results=quota_per_type,
                )
                total_created += created
                total_skipped += skipped
                warnings.extend(type_warnings)

        batch.total_leads = total_created
        await db.commit()

        logger.info(
            f"Google Places import terminé — {total_created} créés, "
            f"{total_skipped} ignorés (location={location})"
        )
        return {
            "batch_id": batch.id,
            "imported": total_created,
            "skipped": total_skipped,
            "warnings": warnings,
            "source": "google_places",
            "location": location,
        }

    async def _import_type(
        self,
        client: httpx.AsyncClient,
        db: AsyncSession,
        batch_id: int,
        query: str,
        lead_type: LeadType,
        max_results: int,
    ) -> tuple[int, int, list[str]]:
        """Parcourt les pages de résultats pour un type donné."""
        created = 0
        skipped = 0
        warnings: list[str] = []
        next_page_token: Optional[str] = None

        while (created + skipped) < max_results:
            # Première page ou page suivante
            if next_page_token:
                # Google impose un délai avant d'utiliser le next_page_token
                await asyncio.sleep(2)
                params = {"pagetoken": next_page_token, "key": self.api_key}
            else:
                params = {
                    "query": query,
                    "key": self.api_key,
                    "language": "fr",
                    "region": "fr",
                }

            data = None
            for attempt in range(4):
                try:
                    resp = await client.get(PLACES_TEXT_SEARCH, params=params)
                    resp.raise_for_status()
                    data = resp.json()
                except Exception as exc:
                    logger.error(f"Google Places API erreur pour '{query}': {exc}")
                    warnings.append(f"Erreur Google Places pour '{query}'")
                    break

                status = data.get("status")
                if next_page_token and status == "INVALID_REQUEST" and attempt < 3:
                    await asyncio.sleep(2 + attempt)
                    continue
                if status == "DEADLINE_EXCEEDED" and attempt < 2:
                    await asyncio.sleep(1 + attempt)
                    continue
                break

            if data is None:
                break

            status = data.get("status")
            if status == "REQUEST_DENIED":
                raise PermissionError(
                    f"Google Places : accès refusé — vérifiez GOOGLE_PLACES_API_KEY. "
                    f"Message : {data.get('error_message', '')}"
                )
            if status not in ("OK", "ZERO_RESULTS"):
                warning = (
                    f"Google Places a interrompu les pages suivantes pour '{query}' "
                    f"(status={status}). Les résultats déjà trouvés sont conservés."
                )
                warnings.append(warning)
                logger.warning(warning)
                break

            for place in data.get("results", []):
                if (created + skipped) >= max_results:
                    break

                place_id = place.get("place_id", "")

                # Dédoublonnage par google_place_id
                existing = await db.execute(
                    select(Lead).where(Lead.google_place_id == place_id)
                )
                if existing.scalar_one_or_none():
                    skipped += 1
                    continue

                city, postal_code = _parse_address(place.get("formatted_address", ""))

                lead = Lead(
                    name=place.get("name", "Établissement inconnu"),
                    lead_type=lead_type,
                    address=place.get("formatted_address"),
                    city=city,
                    postal_code=postal_code,
                    google_place_id=place_id,
                    google_rating=place.get("rating"),
                    google_reviews_count=place.get("user_ratings_total"),
                    # website et phone nécessitent un appel Place Details (payant)
                    # → enrichissement ultérieur
                    website=None,
                    phone=None,
                    source="google_places",
                    batch_id=batch_id,
                    status=LeadStatus.NEW,
                )
                lead.update_score()
                db.add(lead)
                created += 1

            next_page_token = data.get("next_page_token")
            if not next_page_token:
                break

        await db.flush()
        logger.info(f"[Google Places] '{query}': {created} créés, {skipped} ignorés")
        return created, skipped, warnings


def _parse_address(formatted_address: str) -> tuple[Optional[str], Optional[str]]:
    """
    Extrait ville et code postal depuis une adresse Google Maps.
    Exemple : "12 Rue de la Paix, 33000 Bordeaux, France"
    """
    city: Optional[str] = None
    postal_code: Optional[str] = None

    if not formatted_address:
        return city, postal_code

    parts = [p.strip() for p in formatted_address.split(",")]
    for part in parts:
        tokens = part.strip().split(" ", 1)
        if len(tokens) == 2 and tokens[0].isdigit() and len(tokens[0]) == 5:
            postal_code = tokens[0]
            city = tokens[1].strip()
            break

    return city, postal_code
