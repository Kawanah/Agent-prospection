"""
Routes API — Nouvelles sources d'import de leads.

Endpoints :
  POST /api/sources/google-places/import  → Import via Google Places API
  POST /api/sources/sirene/import         → Import via API Sirene / INSEE (gratuit)
  POST /api/sources/datatourisme/import   → Import via API DATAtourisme
  POST /api/sources/pappers/import        → Import via Pappers.fr (dirigeants + nouvelles structures)
  GET  /api/sources/sirene/naf-codes      → Liste des codes NAF disponibles
  GET  /api/sources/datatourisme/types    → Liste des types DATAtourisme disponibles
  GET  /api/sources/pappers/naf-codes     → Liste des codes NAF Pappers disponibles
"""

import shutil
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Optional

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    BackgroundTasks,
    UploadFile,
    File,
    Query,
)
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.database import get_db
from app.services.google_places_source_service import GooglePlacesSourceService
from app.services.sirene_source_service import SireneSourceService, NAF_CODES
from app.services.datatourisme_source_service import (
    DatatourismeSourceService,
    OBJECT_TYPE_MAP,
)
from app.services.pappers_source_service import PappersSourceService, NAF_CODES_PAPPERS

router = APIRouter()


# ─── Schémas de requête ───────────────────────────────────────────────────────


class GooglePlacesImportRequest(BaseModel):
    lead_types: list[str] = Field(
        default=["hotel", "camping"],
        description="Types d'établissements : hotel, camping, gite, chambre_hotes, residence, activite, other",
    )
    location: str = Field(
        ...,
        description="Ville ou zone géographique ex : 'Bordeaux', 'Gironde', 'Côte d\\'Azur'",
        min_length=2,
        max_length=100,
    )
    radius_km: int = Field(
        default=30, ge=1, le=200, description="Rayon de recherche en km"
    )
    max_results: int = Field(
        default=200, ge=1, le=1000, description="Plafond de leads à importer"
    )


class SireneImportRequest(BaseModel):
    naf_codes: list[str] = Field(
        default=["5510Z", "5520Z"],
        description="Codes NAF à importer",
    )
    department: str = Field(
        ...,
        description="Code département ex : '33', '06', '75'",
        min_length=2,
        max_length=3,
    )
    max_results: int = Field(
        default=500, ge=1, le=2000, description="Plafond de leads à importer"
    )
    new_only: bool = Field(
        default=False,
        description="Si True : importe uniquement les entreprises créées dans les 12 derniers mois",
    )


class DatatourismeImportRequest(BaseModel):
    object_types: list[str] = Field(
        default=["accommodation"],
        description="Types d'objets : accommodation, hotel, camping, activity",
    )
    department: str = Field(
        ...,
        description="Code département ex : '33', '06'",
        min_length=2,
        max_length=3,
    )
    max_results: int = Field(
        default=300, ge=1, le=1000, description="Plafond de leads à importer"
    )


# ─── Google Places ─────────────────────────────────────────────────────────────


@router.post("/google-places/import", summary="Import depuis Google Places API")
async def import_google_places(
    body: GooglePlacesImportRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Importe des établissements depuis Google Maps Platform.

    Couvre tous les types (classés ou non) : hôtels, campings, gîtes,
    chambres d'hôtes, prestataires d'activités, nouveaux établissements.

    ⚠️ Nécessite GOOGLE_PLACES_API_KEY dans .env
    Coût estimé : ~0,07 $ pour 200 résultats
    """
    if not body.lead_types:
        raise HTTPException(
            status_code=422, detail="Sélectionnez au moins un type d'établissement"
        )

    service = GooglePlacesSourceService()
    try:
        result = await service.search_and_import(
            db=db,
            lead_types=body.lead_types,
            location=body.location,
            radius_km=body.radius_km,
            max_results=body.max_results,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    return {
        **result,
        "message": (
            f"{result['imported']} établissements importés depuis Google Places "
            f"({body.location}). Pensez à les enrichir pour récupérer emails et téléphones."
        ),
    }


# ─── Sirene / INSEE ────────────────────────────────────────────────────────────


@router.post("/sirene/import", summary="Import depuis l'API Sirene (INSEE)")
async def import_sirene(
    body: SireneImportRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Importe des entreprises depuis l'API Sirene (recherche-entreprises.api.gouv.fr).

    ✅ Gratuit — pas de clé API requise.

    Avantage clé : détecte les nouvelles immatriculations (< 1 an).
    Ces entreprises viennent d'ouvrir et n'ont probablement pas encore de site web.
    """
    if not body.naf_codes:
        raise HTTPException(status_code=422, detail="Sélectionnez au moins un code NAF")

    service = SireneSourceService()
    try:
        result = await service.search_and_import(
            db=db,
            naf_codes=body.naf_codes,
            department=body.department,
            max_results=body.max_results,
            new_only=body.new_only,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    new_label = " (nouvelles immatriculations uniquement)" if body.new_only else ""
    return {
        **result,
        "message": (
            f"{result['imported']} entreprises importées depuis Sirene"
            f"{new_label} — dép. {body.department}."
        ),
    }


@router.get("/sirene/naf-codes", summary="Liste des codes NAF disponibles")
async def list_naf_codes():
    """Retourne la liste des codes NAF supportés pour l'import Sirene."""
    return {
        "naf_codes": [
            {"code": code, "label": info["label"], "lead_type": info["lead_type"].value}
            for code, info in NAF_CODES.items()
        ]
    }


# ─── DATAtourisme ──────────────────────────────────────────────────────────────


@router.post("/datatourisme/import", summary="Import depuis DATAtourisme")
async def import_datatourisme(
    body: DatatourismeImportRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Importe des points d'intérêt touristiques depuis DATAtourisme.

    Couvre le segment absent d'Atout France :
    gîtes, meublés, chambres d'hôtes, hébergements insolites, activités outdoor.

    ⚠️ Nécessite DATATOURISME_API_KEY dans .env
    Inscription gratuite : https://www.datatourisme.fr/obtenir-et-utiliser-la-donnee/
    """
    if not body.object_types:
        raise HTTPException(
            status_code=422, detail="Sélectionnez au moins un type d'objet"
        )

    service = DatatourismeSourceService()
    try:
        result = await service.search_and_import(
            db=db,
            object_types=body.object_types,
            department=body.department,
            max_results=body.max_results,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    return {
        **result,
        "message": (
            f"{result['imported']} établissements importés depuis DATAtourisme — "
            f"dép. {body.department}."
        ),
    }


@router.get("/datatourisme/types", summary="Liste des types DATAtourisme disponibles")
async def list_datatourisme_types():
    """Retourne la liste des types d'objets supportés pour l'import DATAtourisme."""
    return {
        "object_types": [
            {
                "key": key,
                "schema_type": schema_type,
                "lead_type": lead_type.value,
            }
            for key, (schema_type, lead_type) in OBJECT_TYPE_MAP.items()
        ]
    }


# ─── Pappers ───────────────────────────────────────────────────────────────────


class PappersImportRequest(BaseModel):
    naf_codes: list[str] = Field(
        default=["5510Z", "5520Z"],
        description="Codes NAF à importer (hospitalité)",
    )
    department: str = Field(
        ...,
        description="Code département ex : '33', '06', '75'",
        min_length=2,
        max_length=3,
    )
    max_results: int = Field(
        default=200, ge=1, le=1000, description="Plafond de leads à importer"
    )
    new_only: bool = Field(
        default=True,
        description="Si True : nouvelles structures uniquement (créées récemment)",
    )
    months_back: int = Field(
        default=6,
        ge=1,
        le=24,
        description="Fenêtre temporelle en mois pour 'new_only'",
    )


@router.post(
    "/pappers/import",
    summary="Import depuis Pappers.fr (nouvelles structures + dirigeants)",
)
async def import_pappers(
    body: PappersImportRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Importe des entreprises depuis Pappers.fr.

    **Cas d'usage principal :**
    Trouver des nouvelles structures hospitalité qui n'ont pas encore de site web.
    Ces prospects sont idéaux : ils viennent d'ouvrir et ont un besoin immédiat.

    **Bonus Pappers :** les dirigeants sont inclus directement dans la réponse
    (nom, prénom, qualité) — pas besoin d'enrichissement supplémentaire.

    ⚠️ Nécessite PAPPERS_API_KEY dans .env
    """
    if not body.naf_codes:
        raise HTTPException(status_code=422, detail="Sélectionnez au moins un code NAF")

    service = PappersSourceService()
    try:
        result = await service.search_and_import(
            db=db,
            naf_codes=body.naf_codes,
            department=body.department,
            max_results=body.max_results,
            new_only=body.new_only,
            months_back=body.months_back,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    finally:
        await service.close()

    label = f" (nouvelles {body.months_back} derniers mois)" if body.new_only else ""
    new_info = (
        f" dont {result['new_no_website']} sans site web 🔥"
        if result["new_no_website"]
        else ""
    )

    return {
        **result,
        "message": (
            f"{result['imported']} structures importées depuis Pappers{label} — "
            f"dép. {body.department}{new_info}."
        ),
    }


@router.get("/pappers/naf-codes", summary="Liste des codes NAF Pappers disponibles")
async def list_pappers_naf_codes():
    """Retourne la liste des codes NAF supportés pour l'import Pappers."""
    return {
        "naf_codes": [
            {"code": code, "label": info["label"], "lead_type": info["lead_type"].value}
            for code, info in NAF_CODES_PAPPERS.items()
        ]
    }


# ─── Import CSV RCS (Nouvelles Entreprises) ──────────────────────────────────


@router.post(
    "/rcs/import", summary="Import CSV d'inscriptions RCS (nouvelles entreprises)"
)
async def import_rcs_csv(
    file: UploadFile = File(..., description="Fichier CSV d'inscriptions RCS"),
    limit: Optional[int] = Query(None, description="Limite de lignes"),
    db: AsyncSession = Depends(get_db),
):
    """
    Importe des nouvelles entreprises depuis un fichier CSV (export RCS / BODACC).

    Chaque lead importé est automatiquement marqué comme **nouvelle entreprise**
    avec un score RCS dédié (0-5 points).

    **Colonnes détectées automatiquement** : SIREN, Dénomination, Forme juridique,
    Capital, Adresse, Code postal, Ville, Date de création, Code NAF, Objet social.

    ✅ Gratuit — aucune API externe requise pour l'import.
    """
    from app.services.rcs_import_service import import_rcs_csv as do_import
    from app.models.import_batch import ImportBatch
    from datetime import datetime

    filename = file.filename or "rcs_upload.csv"
    extension = Path(filename).suffix.lower()

    if extension not in (".csv", ".xlsx", ".xls"):
        raise HTTPException(
            status_code=400,
            detail=f"Format non supporté : {extension}. Utilisez .csv",
        )

    try:
        with NamedTemporaryFile(delete=False, suffix=extension) as tmp:
            shutil.copyfileobj(file.file, tmp)
            tmp_path = tmp.name

        # Créer le lot d'import
        date_str = datetime.now().strftime("%d/%m/%Y %H:%M")
        base_name = (
            filename.rsplit(".", 1)[0].replace("_", " ").replace("-", " ").title()
        )
        batch = ImportBatch(name=f"RCS — {base_name} — {date_str}", source="rcs_import")
        db.add(batch)
        await db.flush()

        result = await do_import(db, tmp_path, limit=limit, batch_id=batch.id)
        batch.total_leads = result["imported"]
        await db.commit()

        Path(tmp_path).unlink(missing_ok=True)

        return {
            **result,
            "message": (
                f"{result['imported']} nouvelles entreprises importées depuis CSV RCS. "
                f"Score RCS calculé. Enrichissez-les pour compléter les données (BODACC, Pappers)."
            ),
        }

    except Exception as e:
        logger.error(f"Erreur import RCS : {e}")
        raise HTTPException(status_code=500, detail=f"Erreur import : {str(e)}")
    finally:
        file.file.close()
