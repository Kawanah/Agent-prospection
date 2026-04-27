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
from app.models.import_batch import ImportBatch
from app.models.message import Message, MessageStatus
from app.models.campaign import Campaign
from app.schemas.lead import LeadResponse, LeadListResponse, ImportResult
from app.services.import_service import import_file

router = APIRouter()


async def _create_batch(db: AsyncSession, filename: str, source: str) -> ImportBatch:
    """Crée un lot d'import avec un nom automatique."""
    from datetime import datetime

    date_str = datetime.now().strftime("%d/%m/%Y %H:%M")
    # Nom propre : enlever l'extension du fichier
    base_name = filename.rsplit(".", 1)[0].replace("_", " ").replace("-", " ").title()
    batch = ImportBatch(name=f"{base_name} — {date_str}", source=source)
    db.add(batch)
    await db.flush()  # Pour obtenir l'ID
    return batch


@router.get("/", response_model=LeadListResponse)
async def list_leads(
    page: int = Query(1, ge=1, description="Numéro de page"),
    per_page: int = Query(20, ge=1, le=100, description="Leads par page"),
    status: Optional[LeadStatus] = Query(None, description="Filtrer par statut"),
    lead_type: Optional[LeadType] = Query(None, description="Filtrer par type"),
    min_score: Optional[int] = Query(None, ge=0, le=100, description="Score minimum"),
    city: Optional[str] = Query(None, description="Filtrer par ville"),
    has_website: Optional[bool] = Query(None, description="A un site web ?"),
    sort_by: Optional[str] = Query(None, description="Tri : score, created_at, name"),
    sort_order: Optional[str] = Query("desc", description="Ordre : asc ou desc"),
    batch_id: Optional[int] = Query(None, description="Filtrer par lot d'import"),
    star_rating: Optional[str] = Query(
        None, description="Filtrer par étoiles (ex: '3' pour 3 étoiles)"
    ),
    is_nouvelle_entreprise: Optional[bool] = Query(
        None, description="Filtrer nouvelles entreprises"
    ),
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
    if batch_id is not None:
        query = query.where(Lead.batch_id == batch_id)
    if star_rating:
        query = query.where(Lead.star_rating.ilike(f"{star_rating} étoile%"))
    if is_nouvelle_entreprise is not None:
        query = query.where(Lead.is_nouvelle_entreprise == is_nouvelle_entreprise)

    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    sort_columns = {
        "score": Lead.score,
        "created_at": Lead.created_at,
        "name": Lead.name,
        "status": Lead.status,
    }
    sort_col = sort_columns.get(sort_by, Lead.score)
    order = sort_col.asc() if sort_order == "asc" else sort_col.desc()

    offset = (page - 1) * per_page
    query = query.order_by(order).offset(offset).limit(per_page)

    result = await db.execute(query)
    leads = result.scalars().all()

    return LeadListResponse(
        total=total,
        page=page,
        per_page=per_page,
        leads=[LeadResponse.model_validate(lead) for lead in leads],
    )


@router.get("/names")
async def get_lead_names(
    ids: str = Query(..., description="IDs séparés par des virgules (ex: 1,2,3)"),
    db: AsyncSession = Depends(get_db),
):
    """Retourne les noms de leads par ID — endpoint léger pour éviter les requêtes N+1."""
    try:
        id_list = [int(x) for x in ids.split(",") if x.strip()]
    except ValueError:
        raise HTTPException(status_code=422, detail="IDs invalides")
    if len(id_list) > 200:
        raise HTTPException(status_code=400, detail="Maximum 200 IDs par requête")

    result = await db.execute(select(Lead.id, Lead.name).where(Lead.id.in_(id_list)))
    return {str(row[0]): row[1] for row in result.fetchall()}


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
            "nouvelle_entreprise",
            "siren",
            "forme_juridique",
            "capital",
            "objet_social",
            "score_rcs",
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
                lead.is_nouvelle_entreprise,
                lead.siren or "",
                lead.forme_juridique or "",
                lead.capital or "",
                lead.objet_social or "",
                lead.rcs_score if lead.rcs_score is not None else "",
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

    # Stats nouvelles entreprises
    ne_total_result = await db.execute(
        select(func.count(Lead.id)).where(Lead.is_nouvelle_entreprise == True)
    )
    ne_enriched_result = await db.execute(
        select(func.count(Lead.id)).where(
            Lead.is_nouvelle_entreprise == True,
            Lead.status == LeadStatus.ENRICHED,
        )
    )

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
        "nouvelles_entreprises": {
            "total": ne_total_result.scalar(),
            "enriched": ne_enriched_result.scalar(),
        },
    }


@router.get("/batches")
async def list_batches(db: AsyncSession = Depends(get_db)):
    """Retourne les lots d'import avec leurs statistiques."""
    from datetime import date

    result = await db.execute(
        select(ImportBatch).order_by(ImportBatch.created_at.desc())
    )
    batches = result.scalars().all()

    out = []
    for batch in batches:
        # Leads de ce lot
        leads_q = await db.execute(select(Lead).where(Lead.batch_id == batch.id))
        leads = leads_q.scalars().all()

        enriched = sum(1 for l in leads if l.status and l.status.value == "enriched")
        contacted = sum(
            1
            for l in leads
            if l.status and l.status.value in ("contacted", "replied", "converted")
        )

        depts = {}
        types = set()
        for l in leads:
            if l.postal_code:
                pc = str(l.postal_code).strip()
                # Corse : 2A/2B, DOM-TOM : 97x
                if pc.startswith("20") and len(pc) == 5:
                    dept = "2A" if pc < "20200" else "2B"
                elif pc[:2] == "97" and len(pc) == 5:
                    dept = pc[:3]
                else:
                    dept = pc[:2]
                depts[dept] = depts.get(dept, 0) + 1
            if l.lead_type:
                types.add(l.lead_type.value)

        top_depts = [d for d, _ in sorted(depts.items(), key=lambda x: -x[1])[:3]]

        out.append(
            {
                "id": batch.id,
                "name": batch.name,
                "source": batch.source,
                "created_at": batch.created_at.isoformat(),
                "total_leads": len(leads),
                "enriched": enriched,
                "contacted": contacted,
                "departments": top_depts,
                "types": list(types),
            }
        )

    return out


@router.get("/campaign-status")
async def get_leads_campaign_status(
    ids: str = Query(
        "",
        description="IDs séparés par des virgules (vide = tous les leads en campagne)",
    ),
    db: AsyncSession = Depends(get_db),
):
    """Retourne le statut campagne de chaque lead : campagne, statut du message."""
    query = (
        select(
            Message.lead_id,
            Campaign.id.label("campaign_id"),
            Campaign.name.label("campaign_name"),
            Message.status.label("message_status"),
        )
        .join(Campaign, Campaign.id == Message.campaign_id)
        .where(Message.lead_id.isnot(None), Message.campaign_id.isnot(None))
        .order_by(Message.created_at.desc())
    )

    if ids:
        try:
            id_list = [int(x) for x in ids.split(",") if x.strip()]
            query = query.where(Message.lead_id.in_(id_list))
        except ValueError:
            pass

    result = await db.execute(query)
    rows = result.fetchall()

    # Un lead peut avoir plusieurs messages — on prend le plus récent par lead
    out = {}
    for row in rows:
        lid = str(row.lead_id)
        if lid not in out:
            out[lid] = {
                "campaign_id": row.campaign_id,
                "campaign_name": row.campaign_name,
                "message_status": row.message_status.value
                if hasattr(row.message_status, "value")
                else row.message_status,
            }
    return out


@router.get("/{lead_id}/strong-arguments")
async def get_lead_strong_arguments(lead_id: int, db: AsyncSession = Depends(get_db)):
    """
    Retourne les arguments forts détectés pour un lead, triés par impact.
    """
    from app.services.ai_service import AIService

    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead non trouvé")

    args = AIService._detect_strong_arguments(lead)
    return {"lead_id": lead_id, "arguments": args}


@router.patch("/{lead_id}/notes")
async def update_lead_notes(
    lead_id: int, payload: dict, db: AsyncSession = Depends(get_db)
):
    """Met à jour la note libre d'un lead."""
    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead non trouvé")
    lead.notes = payload.get("notes", "").strip() or None
    await db.commit()
    return {"id": lead_id, "notes": lead.notes}


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
    batch = await _create_batch(db, resolved.name, "csv")
    result = await import_file(db, str(resolved), limit=limit, batch_id=batch.id)
    batch.total_leads = result.imported
    await db.commit()
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
        batch = await _create_batch(db, filename, "csv")
        result = await import_file(db, tmp_path, limit=limit, batch_id=batch.id)
        batch.total_leads = result.imported
        await db.commit()

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
