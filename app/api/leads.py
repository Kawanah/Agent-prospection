"""
API endpoints pour la gestion des Leads.
"""

import csv
import io
import shutil
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from loguru import logger

from app.database import get_db
from app.models.lead import Lead, LeadStatus, LeadType
from app.schemas.lead import LeadResponse, LeadListResponse, ImportResult
from app.services.import_service import import_file

router = APIRouter()


@router.get("/", response_model=LeadListResponse)
async def list_leads(
    page: int = Query(1, ge=1, description="Numéro de page"),
    per_page: int = Query(20, ge=1, le=100, description="Leads par page"),
    status: Optional[LeadStatus] = Query(None, description="Filtrer par statut"),
    lead_type: Optional[LeadType] = Query(None, description="Filtrer par type"),
    min_score: Optional[int] = Query(None, ge=0, le=100, description="Score minimum"),
    city: Optional[str] = Query(None, description="Filtrer par ville"),
    has_website: Optional[bool] = Query(None, description="A un site web ?"),
    db: AsyncSession = Depends(get_db),
):
    """
    Liste les leads avec pagination et filtres.
    """
    query = select(Lead)

    if status:
        query = query.where(Lead.status == status)
    if lead_type:
        query = query.where(Lead.lead_type == lead_type)
    if min_score is not None:
        query = query.where(Lead.score >= min_score)
    if city:
        query = query.where(Lead.city.ilike(f"%{city}%"))
    if has_website is not None:
        query = query.where(Lead.has_website == has_website)

    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    offset = (page - 1) * per_page
    query = query.order_by(Lead.score.desc()).offset(offset).limit(per_page)

    result = await db.execute(query)
    leads = result.scalars().all()

    return LeadListResponse(
        total=total,
        page=page,
        per_page=per_page,
        leads=[LeadResponse.model_validate(lead) for lead in leads],
    )


@router.get("/export")
async def export_leads_csv(
    status: Optional[LeadStatus] = Query(None),
    lead_type: Optional[LeadType] = Query(None),
    min_score: Optional[int] = Query(None, ge=0, le=100),
    has_website: Optional[bool] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Exporte tous les leads filtrés au format CSV."""
    query = select(Lead)
    if status:
        query = query.where(Lead.status == status)
    if lead_type:
        query = query.where(Lead.lead_type == lead_type)
    if min_score is not None:
        query = query.where(Lead.score >= min_score)
    if has_website is not None:
        query = query.where(Lead.has_website == has_website)
    query = query.order_by(Lead.score.desc())

    result = await db.execute(query)
    leads = result.scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "id",
            "nom",
            "type",
            "ville",
            "code_postal",
            "email",
            "telephone",
            "site_web",
            "score",
            "statut",
            "a_site_web",
        ]
    )
    for lead in leads:
        writer.writerow(
            [
                lead.id,
                lead.name,
                lead.lead_type.value if lead.lead_type else "",
                lead.city or "",
                lead.postal_code or "",
                lead.email or "",
                lead.phone or "",
                lead.website or "",
                lead.score,
                lead.status.value if lead.status else "",
                lead.has_website,
            ]
        )

    output.seek(0)
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8-sig")),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=leads_kawanah.csv"},
    )


@router.get("/stats")
async def get_stats(db: AsyncSession = Depends(get_db)):
    """
    Retourne les statistiques globales des leads.
    """
    total_result = await db.execute(select(func.count(Lead.id)))
    total = total_result.scalar()

    status_query = select(Lead.status, func.count(Lead.id)).group_by(Lead.status)
    status_result = await db.execute(status_query)
    by_status = {row[0].value: row[1] for row in status_result}

    type_query = select(Lead.lead_type, func.count(Lead.id)).group_by(Lead.lead_type)
    type_result = await db.execute(type_query)
    by_type = {row[0].value: row[1] for row in type_result}

    # with_website = has_website confirmé True après enrichissement
    with_website = await db.execute(
        select(func.count(Lead.id)).where(Lead.has_website == True)
    )
    # without_website = has_website confirmé False après enrichissement
    without_website = await db.execute(
        select(func.count(Lead.id)).where(Lead.has_website == False)
    )
    # has_url = URL présente dans la source (data.gouv.fr) mais pas encore vérifiée
    has_url = await db.execute(
        select(func.count(Lead.id)).where(
            Lead.website.isnot(None), Lead.has_website.is_(None)
        )
    )
    # not_analyzed = aucune URL et pas encore enrichi
    not_analyzed = await db.execute(
        select(func.count(Lead.id)).where(
            Lead.website.is_(None), Lead.has_website.is_(None)
        )
    )

    avg_score_result = await db.execute(select(func.avg(Lead.score)))
    avg_score = avg_score_result.scalar() or 0

    hot_leads_result = await db.execute(
        select(func.count(Lead.id)).where(Lead.score >= 80)
    )
    hot_leads = hot_leads_result.scalar()

    return {
        "total": total,
        "by_status": by_status,
        "by_type": by_type,
        "with_website": with_website.scalar(),
        "without_website": without_website.scalar(),
        "has_url": has_url.scalar(),
        "not_analyzed": not_analyzed.scalar(),
        "average_score": round(avg_score, 1),
        "hot_leads": hot_leads,
    }


@router.get("/{lead_id}", response_model=LeadResponse)
async def get_lead(lead_id: int, db: AsyncSession = Depends(get_db)):
    """
    Récupère un lead par son ID.
    """
    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()

    if not lead:
        raise HTTPException(status_code=404, detail="Lead non trouvé")

    return LeadResponse.model_validate(lead)


@router.post("/import", response_model=ImportResult)
async def import_leads_from_path(
    file_path: str = Query(
        ..., description="Chemin vers le fichier Excel/CSV (relatif au dossier data/)"
    ),
    limit: Optional[int] = Query(
        None, description="Limite le nombre de lignes (pour les tests)"
    ),
    db: AsyncSession = Depends(get_db),
):
    """
    Importe des leads depuis un fichier Excel ou CSV présent dans le dossier data/.

    Exemple: /api/leads/import?file_path=hebergements_classes.xlsx&limit=100
    """
    # Résoudre le chemin dans le dossier data/ uniquement (protection path traversal)
    data_dir = (Path(__file__).parent.parent.parent / "data").resolve()
    resolved = (data_dir / file_path).resolve()

    if not str(resolved).startswith(str(data_dir)):
        raise HTTPException(status_code=400, detail="Chemin de fichier invalide")

    if resolved.suffix.lower() not in (".xlsx", ".xls", ".csv"):
        raise HTTPException(
            status_code=400, detail="Format non supporté. Utilisez .xlsx, .xls ou .csv"
        )

    if not resolved.exists():
        raise HTTPException(
            status_code=404, detail=f"Fichier non trouvé dans data/ : {file_path}"
        )

    logger.info(f"Demande d'import (chemin): {resolved}, limit={limit}")
    result = await import_file(db, str(resolved), limit=limit)
    return result


@router.post("/upload", response_model=ImportResult)
async def upload_and_import_leads(
    file: UploadFile = File(..., description="Fichier Excel (.xlsx) ou CSV (.csv)"),
    limit: Optional[int] = Query(
        None, description="Limite le nombre de lignes (pour les tests)"
    ),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload et importe un fichier Excel ou CSV directement via l'API.

    Formats supportés: .xlsx, .xls, .csv
    """
    # Vérifier l'extension
    filename = file.filename or "upload"
    extension = Path(filename).suffix.lower()

    if extension not in (".xlsx", ".xls", ".csv"):
        raise HTTPException(
            status_code=400,
            detail=f"Format non supporté: {extension}. Utilisez .xlsx, .xls ou .csv",
        )

    logger.info(f"Upload reçu: {filename} ({file.content_type})")

    # Sauvegarder le fichier temporairement
    try:
        with NamedTemporaryFile(delete=False, suffix=extension) as tmp:
            shutil.copyfileobj(file.file, tmp)
            tmp_path = tmp.name

        logger.info(f"Fichier sauvegardé temporairement: {tmp_path}")

        # Importer le fichier
        result = await import_file(db, tmp_path, limit=limit)

        # Nettoyer le fichier temporaire
        Path(tmp_path).unlink(missing_ok=True)

        return result

    except Exception as e:
        logger.error(f"Erreur lors de l'upload: {e}")
        raise HTTPException(
            status_code=500, detail=f"Erreur lors de l'import: {str(e)}"
        )

    finally:
        file.file.close()


@router.delete("/{lead_id}")
async def delete_lead(lead_id: int, db: AsyncSession = Depends(get_db)):
    """
    Supprime un lead.
    """
    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()

    if not lead:
        raise HTTPException(status_code=404, detail="Lead non trouvé")

    await db.delete(lead)
    await db.commit()

    return {"message": f"Lead {lead_id} supprimé"}


@router.delete("/")
async def delete_all_leads(
    confirm: bool = Query(
        False, description="Confirmer la suppression de TOUS les leads"
    ),
    confirm_text: str = Query(
        "", description="Saisir exactement 'SUPPRIMER TOUT' pour confirmer"
    ),
    db: AsyncSession = Depends(get_db),
):
    """
    Supprime TOUS les leads de la base de données.
    Nécessite confirm=true ET confirm_text=SUPPRIMER TOUT.
    """
    if not confirm or confirm_text != "SUPPRIMER TOUT":
        raise HTTPException(
            status_code=400,
            detail="Double confirmation requise : ?confirm=true&confirm_text=SUPPRIMER TOUT",
        )

    result = await db.execute(select(func.count(Lead.id)))
    count = result.scalar()

    await db.execute(Lead.__table__.delete())
    await db.commit()

    logger.warning(f"Tous les leads supprimés ({count} leads)")
    return {"message": f"{count} leads supprimés"}
