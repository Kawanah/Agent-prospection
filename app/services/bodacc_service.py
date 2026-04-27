"""
Service BODACC — Publications au Bulletin Officiel des Annonces Civiles et Commerciales.

API gratuite, sans clé : https://bodacc-datadila.opendatasoft.com/api/v2/

Use case : récupérer l'activité déclarée en texte clair lors de l'immatriculation RCS.
Permet de personnaliser les messages de prospection avec l'activité réelle du prospect.
"""

from typing import Optional

import httpx
from loguru import logger


class BodaccService:
    """Interroge l'API BODACC (OpenDataSoft) pour enrichir les nouvelles entreprises."""

    BASE_URL = (
        "https://bodacc-datadila.opendatasoft.com/api/v2"
        "/catalog/datasets/annonces-commerciales/records"
    )

    def __init__(self):
        self.client = httpx.AsyncClient(timeout=15)

    async def close(self):
        await self.client.aclose()

    async def search_by_siren(self, siren: str) -> Optional[dict]:
        """
        Recherche les publications BODACC d'immatriculation pour un SIREN donné.

        Retourne le premier résultat d'immatriculation trouvé, ou None.
        """
        siren = siren.strip().replace(" ", "")
        if not siren or len(siren) < 9:
            return None

        try:
            resp = await self.client.get(
                self.BASE_URL,
                params={
                    "where": (
                        f'registre_du_commerce_et_des_societes LIKE "%{siren}%"'
                        ' AND type_avis="immatriculation"'
                    ),
                    "limit": 5,
                    "order_by": "dateparution DESC",
                },
            )
            resp.raise_for_status()
            data = resp.json()

            records = data.get("results", [])
            if not records:
                # Fallback : chercher par numero_identification
                resp2 = await self.client.get(
                    self.BASE_URL,
                    params={
                        "where": f'numero_identification LIKE "%{siren}%"',
                        "limit": 5,
                        "order_by": "dateparution DESC",
                    },
                )
                resp2.raise_for_status()
                records = resp2.json().get("results", [])

            if not records:
                logger.debug(f"BODACC: aucune publication trouvée pour SIREN {siren}")
                return None

            record = records[0]
            logger.info(f"BODACC: publication trouvée pour SIREN {siren}")
            return record

        except httpx.HTTPError as e:
            logger.warning(f"BODACC: erreur HTTP pour SIREN {siren}: {e}")
            return None

    def extract_activite(self, record: dict) -> Optional[str]:
        """Extrait l'activité déclarée depuis un enregistrement BODACC."""
        if not record:
            return None
        # Champs possibles dans la réponse BODACC
        for field in ("activite", "descriptif", "commentaire"):
            val = record.get(field)
            if val and isinstance(val, str) and len(val.strip()) > 5:
                return val.strip()
        return None

    def extract_publication_date(self, record: dict) -> Optional[str]:
        """Extrait la date de publication (format YYYY-MM-DD)."""
        if not record:
            return None
        return record.get("dateparution")

    async def enrich_lead(self, lead, db) -> bool:
        """
        Enrichit un lead avec les données BODACC.

        Retourne True si des données ont été trouvées et ajoutées.
        """
        from datetime import date as date_type

        siren = lead.siren or lead.external_id
        if not siren:
            return False

        record = await self.search_by_siren(siren)
        if not record:
            return False

        updated = False

        activite = self.extract_activite(record)
        if activite and not lead.bodacc_activite:
            lead.bodacc_activite = activite
            updated = True

        pub_date = self.extract_publication_date(record)
        if pub_date and not lead.bodacc_publication_date:
            try:
                lead.bodacc_publication_date = date_type.fromisoformat(pub_date)
                updated = True
            except (ValueError, TypeError):
                pass

        if updated:
            logger.info(
                f"BODACC: lead '{lead.name}' enrichi "
                f"(activité: {bool(activite)}, date: {bool(pub_date)})"
            )

        return updated
