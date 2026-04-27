"""
Source Sirene / INSEE — Import via l'API recherche-entreprises.api.gouv.fr

Avantages :
- Gratuit, sans clé API
- Couvre toutes les entreprises françaises
- Filtre par code NAF (activité) + département
- Détecte les nouvelles immatriculations (< 1 an = prospect chaud)
- Couvre gîtes, chambres d'hôtes, activités — absents d'Atout France

Codes NAF pertinents :
    5510Z — Hôtels et hébergements similaires
    5520Z — Hébergements touristiques de courte durée (gîtes, B&B…)
    5530Z — Terrains de camping
    7990Z — Autres services de réservation et activités connexes
    9329Z — Autres activités récréatives et de loisirs

Doc API : https://recherche-entreprises.api.gouv.fr/docs
"""

from datetime import datetime, date, timedelta
from typing import Optional

import httpx
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.import_batch import ImportBatch
from app.models.lead import Lead, LeadStatus, LeadType

# ─── API (pas de clé requise) ─────────────────────────────────────────────────
SIRENE_API = "https://recherche-entreprises.api.gouv.fr/search"

# ─── Codes NAF disponibles pour l'import ──────────────────────────────────────
NAF_CODES = {
    "5510Z": {
        "label": "Hôtels et hébergements similaires",
        "lead_type": LeadType.HOTEL,
    },
    "5520Z": {
        "label": "Hébergements touristiques de courte durée",
        "lead_type": LeadType.GITE,
    },
    "5530Z": {
        "label": "Terrains de camping et parcs pour caravanes",
        "lead_type": LeadType.CAMPING,
    },
    "7990Z": {
        "label": "Autres services de réservation",
        "lead_type": LeadType.ACTIVITE,
    },
    "9329Z": {
        "label": "Autres activités récréatives et de loisirs",
        "lead_type": LeadType.ACTIVITE,
    },
}


class SireneSourceService:
    """
    Import de leads depuis l'API Sirene (recherche-entreprises.api.gouv.fr).

    Usage :
        service = SireneSourceService()
        result = await service.search_and_import(
            db=db,
            naf_codes=["5510Z", "5520Z"],
            department="33",
            max_results=500,
            new_only=False,
        )
    """

    async def search_and_import(
        self,
        db: AsyncSession,
        naf_codes: list[str],
        department: str,
        max_results: int = 500,
        new_only: bool = False,
    ) -> dict:
        """
        Importe les entreprises actives du secteur tourisme/hébergement.

        Params :
            naf_codes   : liste de codes NAF ex. ["5510Z", "5520Z"]
            department  : code département ex. "33", "06"
            max_results : plafond total de leads à importer
            new_only    : si True, importe uniquement les créations < 1 an
        """
        # Valider les codes NAF
        unknown = [c for c in naf_codes if c not in NAF_CODES]
        if unknown:
            raise ValueError(
                f"Codes NAF inconnus : {unknown}. "
                f"Codes supportés : {list(NAF_CODES.keys())}"
            )

        batch = ImportBatch(
            name=(
                f"Sirene — Dép. {department} — "
                f"{', '.join(naf_codes)}"
                f"{' (nouvelles immat.)' if new_only else ''} — "
                f"{datetime.now().strftime('%d/%m/%Y %H:%M')}"
            ),
            source="sirene",
        )
        db.add(batch)
        await db.flush()

        total_created = 0
        total_skipped = 0
        quota_per_naf = max(1, max_results // len(naf_codes))

        async with httpx.AsyncClient(timeout=30) as client:
            for naf in naf_codes:
                created, skipped = await self._import_naf(
                    client=client,
                    db=db,
                    batch_id=batch.id,
                    naf_code=naf,
                    department=department,
                    max_results=quota_per_naf,
                    new_only=new_only,
                )
                total_created += created
                total_skipped += skipped

        batch.total_leads = total_created
        await db.commit()

        logger.info(
            f"Sirene import terminé — {total_created} créés, "
            f"{total_skipped} ignorés (dép.{department})"
        )
        return {
            "batch_id": batch.id,
            "imported": total_created,
            "skipped": total_skipped,
            "source": "sirene",
            "department": department,
            "new_only": new_only,
        }

    async def _import_naf(
        self,
        client: httpx.AsyncClient,
        db: AsyncSession,
        batch_id: int,
        naf_code: str,
        department: str,
        max_results: int,
        new_only: bool,
    ) -> tuple[int, int]:
        """Parcourt les pages de l'API Sirene pour un code NAF donné."""
        created = 0
        skipped = 0
        page = 1
        per_page = 25
        cutoff_date = date.today() - timedelta(days=365)
        naf_info = NAF_CODES[naf_code]

        while (created + skipped) < max_results:
            try:
                resp = await client.get(
                    SIRENE_API,
                    params={
                        "activite_principale": naf_code,
                        "departement": department,
                        "page": page,
                        "per_page": per_page,
                        "etat_administratif": "A",  # Entreprises actives uniquement
                    },
                )
                resp.raise_for_status()
                data = resp.json()
            except Exception as exc:
                logger.error(
                    f"Sirene API erreur [{naf_code} / dép.{department}]: {exc}"
                )
                break

            results = data.get("results", [])
            if not results:
                break

            for company in results:
                if (created + skipped) >= max_results:
                    break

                siret = company.get("siret", "")
                siren = company.get("siren", "")

                # Filtre nouvelles immatriculations
                if new_only:
                    date_str = company.get("date_creation", "")
                    if date_str:
                        try:
                            date_creation = datetime.strptime(
                                date_str, "%Y-%m-%d"
                            ).date()
                            if date_creation < cutoff_date:
                                skipped += 1
                                continue
                        except ValueError:
                            pass

                # Dédoublonnage par SIRET
                existing = await db.execute(
                    select(Lead).where(Lead.external_id == siret)
                )
                if existing.scalar_one_or_none():
                    skipped += 1
                    continue

                siege = company.get("siege", {})

                name = _best_name(company)
                city = _clean(siege.get("libelle_commune"))
                postal_code = _clean(siege.get("code_postal"))
                address = _build_address(siege)

                date_creation_str = company.get("date_creation")
                established = None
                if date_creation_str:
                    try:
                        established = datetime.strptime(
                            date_creation_str, "%Y-%m-%d"
                        ).date()
                    except ValueError:
                        pass

                lead = Lead(
                    name=name,
                    lead_type=naf_info["lead_type"],
                    address=address,
                    city=city,
                    postal_code=postal_code,
                    external_id=siret,
                    source="sirene",
                    batch_id=batch_id,
                    status=LeadStatus.NEW,
                    established_date=established,
                    notes=f"SIREN: {siren} | NAF: {naf_code} — {naf_info['label']}",
                )
                lead.update_score()
                db.add(lead)
                created += 1

            # Arrêter si on a atteint la dernière page
            total_api = data.get("total_results", 0)
            if page * per_page >= total_api:
                break
            page += 1

        await db.flush()
        logger.info(
            f"[Sirene] NAF {naf_code} dép.{department}: {created} créés, {skipped} ignorés"
        )
        return created, skipped


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _best_name(company: dict) -> str:
    """Choisit le meilleur nom disponible pour l'entreprise."""
    return (
        company.get("nom_complet")
        or company.get("nom_raison_sociale")
        or company.get("sigle")
        or "Entreprise inconnue"
    )


def _clean(value: Optional[str]) -> Optional[str]:
    return value.strip() if value and value.strip() else None


def _build_address(siege: dict) -> Optional[str]:
    """Reconstruit une adresse lisible depuis les champs INSEE."""
    parts = [
        siege.get("numero_voie"),
        siege.get("type_voie"),
        siege.get("libelle_voie"),
        siege.get("complement_adresse"),
    ]
    line = " ".join(p for p in parts if p and p.strip())
    return line.strip() or None
