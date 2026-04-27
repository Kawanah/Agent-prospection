"""
Source DATAtourisme — Import via l'API nationale du tourisme français.

Couvre le segment absent d'Atout France :
gîtes (Gîtes de France), meublés de tourisme, chambres d'hôtes,
hébergements insolites, prestataires d'activités.

Données : Agrégateur national open data tourisme
Site     : https://www.datatourisme.fr
API      : https://diffusiondata.datatourisme.fr/api/v1/query/{API_KEY}

Clé API requise : DATATOURISME_API_KEY dans .env
Inscription gratuite : https://www.datatourisme.fr/obtenir-et-utiliser-la-donnee/

Types d'objets DATAtourisme utilisés :
    Accommodation            → hébergements (gîtes, meublés, chambres d'hôtes)
    FoodEstablishment        → restaurants / tables d'hôtes
    LocalTouristOffice       → offices de tourisme
    SportsAndLeisurePlace    → activités outdoor
    TouristInformationCenter → centres d'info touristique

Référence types : https://www.datatourisme.fr/ontologie/
"""

from datetime import datetime
from typing import Optional

import httpx
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.import_batch import ImportBatch
from app.models.lead import Lead, LeadStatus, LeadType

# ─── URL de l'API DATAtourisme ────────────────────────────────────────────────
DATATOURISME_API = "https://diffusiondata.datatourisme.fr/api/v1/query"

# ─── Mapping type DATAtourisme → LeadType interne ────────────────────────────
OBJECT_TYPE_MAP: dict[str, tuple[str, LeadType]] = {
    "accommodation": (
        "schema:Accommodation",
        LeadType.GITE,
    ),
    "hotel": (
        "schema:Hotel",
        LeadType.HOTEL,
    ),
    "camping": (
        "schema:Campground",
        LeadType.CAMPING,
    ),
    "activity": (
        "schema:SportsActivityLocation",
        LeadType.ACTIVITE,
    ),
}


class DatatourismeSourceService:
    """
    Import de leads depuis l'API DATAtourisme.

    Usage :
        service = DatatourismeSourceService()
        result = await service.search_and_import(
            db=db,
            object_types=["accommodation", "camping"],
            department="33",
            max_results=300,
        )
    """

    def __init__(self) -> None:
        self.api_key = get_settings().datatourisme_api_key

    async def search_and_import(
        self,
        db: AsyncSession,
        object_types: list[str],
        department: str,
        max_results: int = 300,
    ) -> dict:
        """
        Importe les points d'intérêt touristiques depuis DATAtourisme.

        Params :
            object_types : liste ex. ["accommodation", "camping", "activity"]
            department   : code département ex. "33", "06", "2A"
            max_results  : plafond total de leads à importer
        """
        if not self.api_key:
            raise ValueError(
                "DATATOURISME_API_KEY non configurée dans .env. "
                "Inscription gratuite : https://www.datatourisme.fr/obtenir-et-utiliser-la-donnee/"
            )

        unknown = [t for t in object_types if t not in OBJECT_TYPE_MAP]
        if unknown:
            raise ValueError(
                f"Types inconnus : {unknown}. "
                f"Types supportés : {list(OBJECT_TYPE_MAP.keys())}"
            )

        batch = ImportBatch(
            name=(
                f"DATAtourisme — Dép. {department} — "
                f"{', '.join(object_types)} — "
                f"{datetime.now().strftime('%d/%m/%Y %H:%M')}"
            ),
            source="datatourisme",
        )
        db.add(batch)
        await db.flush()

        total_created = 0
        total_skipped = 0
        quota_per_type = max(1, max_results // len(object_types))

        async with httpx.AsyncClient(timeout=60) as client:
            for obj_type in object_types:
                schema_type, lead_type = OBJECT_TYPE_MAP[obj_type]
                created, skipped = await self._import_type(
                    client=client,
                    db=db,
                    batch_id=batch.id,
                    schema_type=schema_type,
                    lead_type=lead_type,
                    department=department,
                    max_results=quota_per_type,
                )
                total_created += created
                total_skipped += skipped

        batch.total_leads = total_created
        await db.commit()

        logger.info(
            f"DATAtourisme import terminé — {total_created} créés, "
            f"{total_skipped} ignorés (dép.{department})"
        )
        return {
            "batch_id": batch.id,
            "imported": total_created,
            "skipped": total_skipped,
            "source": "datatourisme",
            "department": department,
        }

    async def _import_type(
        self,
        client: httpx.AsyncClient,
        db: AsyncSession,
        batch_id: int,
        schema_type: str,
        lead_type: LeadType,
        department: str,
        max_results: int,
    ) -> tuple[int, int]:
        """Requête GraphQL paginée pour un type d'objet touristique."""
        created = 0
        skipped = 0
        after_cursor: Optional[str] = None
        page_size = 50

        while (created + skipped) < max_results:
            query = _build_graphql_query(
                schema_type, department, page_size, after_cursor
            )

            try:
                resp = await client.post(
                    f"{DATATOURISME_API}/{self.api_key}",
                    json={"query": query},
                    headers={"Content-Type": "application/json"},
                )
                resp.raise_for_status()
                data = resp.json()
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 401:
                    raise PermissionError(
                        "DATAtourisme : clé API invalide ou expirée — "
                        "vérifiez DATATOURISME_API_KEY dans .env"
                    )
                logger.error(f"DATAtourisme API erreur: {exc}")
                break
            except Exception as exc:
                logger.error(f"DATAtourisme API erreur: {exc}")
                break

            errors = data.get("errors")
            if errors:
                logger.error(f"DATAtourisme GraphQL erreurs: {errors}")
                break

            poi_data = data.get("data", {}).get("poi", {})
            edges = poi_data.get("edges", [])
            page_info = poi_data.get("pageInfo", {})

            for edge in edges:
                if (created + skipped) >= max_results:
                    break

                node = edge.get("node", {})
                external_id = node.get("@id", "")

                # Dédoublonnage par ID DATAtourisme
                existing = await db.execute(
                    select(Lead).where(Lead.external_id == external_id)
                )
                if existing.scalar_one_or_none():
                    skipped += 1
                    continue

                name, address, city, postal_code, phone, website, email = _parse_node(
                    node
                )

                if not name:
                    skipped += 1
                    continue

                lead = Lead(
                    name=name,
                    lead_type=lead_type,
                    address=address,
                    city=city,
                    postal_code=postal_code,
                    phone=phone,
                    website=website,
                    email=email,
                    external_id=external_id,
                    source="datatourisme",
                    batch_id=batch_id,
                    status=LeadStatus.NEW,
                )
                lead.update_score()
                db.add(lead)
                created += 1

            # Pagination curseur
            if not page_info.get("hasNextPage"):
                break
            after_cursor = page_info.get("endCursor")
            if not after_cursor:
                break

        await db.flush()
        logger.info(
            f"[DATAtourisme] {schema_type} dép.{department}: {created} créés, {skipped} ignorés"
        )
        return created, skipped


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _build_graphql_query(
    schema_type: str,
    department: str,
    first: int,
    after: Optional[str],
) -> str:
    """Construit la requête GraphQL DATAtourisme."""
    after_arg = f', after: "{after}"' if after else ""
    return f"""
    {{
      poi(
        filters: [
          {{ key: "@type", value: "{schema_type}" }}
          {{ key: "isLocatedAt.address.addressDepartment", value: "{department}" }}
        ]
        first: {first}
        {after_arg}
      ) {{
        pageInfo {{
          hasNextPage
          endCursor
        }}
        edges {{
          node {{
            @id
            rdfs:label {{ value }}
            isLocatedAt {{
              address {{
                schema:streetAddress {{ value }}
                schema:postalCode {{ value }}
                schema:addressLocality {{ value }}
              }}
            }}
            hasContact {{
              schema:telephone {{ value }}
              schema:email {{ value }}
              foaf:homepage {{ value }}
            }}
          }}
        }}
      }}
    }}
    """


def _parse_node(node: dict) -> tuple:
    """
    Extrait nom, adresse, ville, CP, téléphone, site web, email d'un nœud DATAtourisme.
    Retourne (name, address, city, postal_code, phone, website, email).
    """
    # Nom
    labels = node.get("rdfs:label", [])
    name: Optional[str] = None
    for label in labels if isinstance(labels, list) else [labels]:
        if isinstance(label, dict):
            name = label.get("value")
            break

    # Adresse
    address: Optional[str] = None
    city: Optional[str] = None
    postal_code: Optional[str] = None

    is_located = node.get("isLocatedAt", [])
    if isinstance(is_located, list) and is_located:
        is_located = is_located[0]
    if isinstance(is_located, dict):
        addr = is_located.get("address", {})
        if isinstance(addr, list) and addr:
            addr = addr[0]
        if isinstance(addr, dict):
            address = _first_value(addr.get("schema:streetAddress"))
            postal_code = _first_value(addr.get("schema:postalCode"))
            city = _first_value(addr.get("schema:addressLocality"))

    # Contact
    phone: Optional[str] = None
    website: Optional[str] = None
    email: Optional[str] = None

    contacts = node.get("hasContact", [])
    if isinstance(contacts, dict):
        contacts = [contacts]
    for contact in contacts or []:
        if not phone:
            phone = _first_value(contact.get("schema:telephone"))
        if not email:
            email = _first_value(contact.get("schema:email"))
        if not website:
            website = _first_value(contact.get("foaf:homepage"))

    return name, address, city, postal_code, phone, website, email


def _first_value(field) -> Optional[str]:
    """Extrait la première valeur d'un champ JSON-LD (scalaire ou liste de dicts)."""
    if not field:
        return None
    if isinstance(field, str):
        return field.strip() or None
    if isinstance(field, list) and field:
        item = field[0]
        if isinstance(item, dict):
            return item.get("value", "").strip() or None
        return str(item).strip() or None
    if isinstance(field, dict):
        return field.get("value", "").strip() or None
    return None
