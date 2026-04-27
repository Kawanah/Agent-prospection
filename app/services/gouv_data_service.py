"""
Service d'import depuis data.gouv.fr — avec checkpoint de reprise.

Stratégie :
  - Téléchargement du CSV Atout France en une fois (cache local)
  - Traitement par lots de 100 lignes avec checkpoint sur l'offset
  - Reprise depuis l'offset sauvegardé en cas d'interruption

Source CSV : https://data.classement.atout-france.fr/static/exportHebergementsClasses/hebergements_classes.csv
21 251 hébergements classés (hôtels, campings, résidences, villages de vacances)
"""

import os
import csv
import io
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Optional, AsyncGenerator

import httpx
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.lead import Lead, LeadStatus, LeadType
from app.models.gouv_import_job import GouvImportJob, JobStatus

# ─── Constantes ───────────────────────────────────────────────────────────────

DATASET_SLUG = "hebergements-touristiques-classes-en-france"
RESOURCE_ID = "3ce290bf-07ec-4d63-b12b-d0496193a535"
CSV_URL = "https://data.classement.atout-france.fr/static/exportHebergementsClasses/hebergements_classes.csv"
GOUV_API = "https://www.data.gouv.fr/api/1"

# Dossier de cache local
CACHE_DIR = Path("data")

# ─── Colonnes réelles du CSV Atout France ────────────────────────────────────
# Colonnes : __id, DATE DE CLASSEMENT, TYPOLOGIE ÉTABLISSEMENT, CLASSEMENT,
#            CATÉGORIE, MENTION, NOM COMMERCIAL, ADRESSE, CODE POSTAL,
#            COMMUNE, SITE INTERNET, TYPE DE SÉJOUR,
#            CAPACITÉ D'ACCUEIL (PERSONNES), NOMBRE DE CHAMBRES,
#            NOMBRE D'EMPLACEMENTS, NOMBRE D'UNITES D'HABITATION, ...

COL = {
    "external_id": "__id",
    "name": "NOM COMMERCIAL",
    "address": "ADRESSE",
    "postal_code": "CODE POSTAL",
    "city": "COMMUNE",
    "website": "SITE INTERNET",
    "lead_type": "TYPOLOGIE ÉTABLISSEMENT",
    "star_rating": "CLASSEMENT",
    "room_count": "NOMBRE DE CHAMBRES",
    "capacity": "CAPACITÉ D'ACCUEIL (PERSONNES)",
    "pitch_count": "NOMBRE D'EMPLACEMENTS",
}

# Mapping TYPOLOGIE ÉTABLISSEMENT (valeurs réelles Atout France) → LeadType
# Dataset : HÔTEL DE TOURISME, CAMPING, RÉSIDENCE DE TOURISME,
#           VILLAGE DE VACANCES, PARC RÉSIDENTIEL DE LOISIRS, AUBERGE COLLECTIVE
TYPE_MAP = {
    "hôtel de tourisme": LeadType.HOTEL,
    "hotel de tourisme": LeadType.HOTEL,
    "camping": LeadType.CAMPING,
    "résidence de tourisme": LeadType.RESIDENCE,
    "residence de tourisme": LeadType.RESIDENCE,
    "village de vacances": LeadType.RESIDENCE,
    "parc résidentiel de loisirs": LeadType.RESIDENCE,
    "parc residentiel": LeadType.RESIDENCE,
    "auberge collective": LeadType.OTHER,
    "auberge de jeunesse": LeadType.OTHER,
}

# Mapping Région → codes de département (pour filtrage par CP)
REGION_DEPTS = {
    "Auvergne-Rhône-Alpes": [
        "01",
        "03",
        "07",
        "15",
        "26",
        "38",
        "42",
        "43",
        "63",
        "69",
        "73",
        "74",
    ],
    "Bourgogne-Franche-Comté": ["21", "25", "39", "58", "70", "71", "89", "90"],
    "Bretagne": ["22", "29", "35", "56"],
    "Centre-Val de Loire": ["18", "28", "36", "37", "41", "45"],
    "Corse": ["2A", "2B", "20"],
    "Grand Est": ["08", "10", "51", "52", "54", "55", "57", "67", "68", "88"],
    "Hauts-de-France": ["02", "59", "60", "62", "80"],
    "Île-de-France": ["75", "77", "78", "91", "92", "93", "94", "95"],
    "Normandie": ["14", "27", "50", "61", "76"],
    "Nouvelle-Aquitaine": [
        "16",
        "17",
        "19",
        "23",
        "24",
        "33",
        "40",
        "47",
        "64",
        "79",
        "86",
        "87",
    ],
    "Occitanie": [
        "09",
        "11",
        "12",
        "30",
        "31",
        "32",
        "34",
        "46",
        "48",
        "65",
        "66",
        "81",
        "82",
    ],
    "Pays de la Loire": ["44", "49", "53", "72", "85"],
    "Provence-Alpes-Côte d'Azur": ["04", "05", "06", "13", "83", "84"],
}


def _get_val(record: dict, col: str) -> Optional[str]:
    """Extrait une valeur proprement (None si vide/tiret)."""
    v = record.get(col)
    if v is None:
        return None
    s = str(v).strip()
    return None if s in ("", "-", "nan", "None", "false", "False") else s


def _to_lead_type(raw: Optional[str]) -> LeadType:
    if not raw:
        return LeadType.OTHER
    key = raw.lower().strip()
    for pattern, lt in TYPE_MAP.items():
        if pattern in key:
            return lt
    return LeadType.OTHER


def _parse_record(record: dict) -> Optional[dict]:
    """Convertit une ligne CSV en dict Lead. Retourne None si nom absent."""
    name = _get_val(record, COL["name"])
    if not name:
        return None

    # Code postal (normaliser : "38000.0" → "38000", "1000" → "01000")
    cp_raw = _get_val(record, COL["postal_code"])
    postal_code = None
    if cp_raw:
        cp_clean = cp_raw.split(".")[0].strip().zfill(5)
        postal_code = cp_clean if len(cp_clean) == 5 else cp_raw

    # Chambres / emplacements / capacité
    def _int(col):
        v = _get_val(record, col)
        if not v:
            return None
        try:
            return int(float(v))
        except (ValueError, TypeError):
            return None

    website_raw = _get_val(record, COL["website"])
    return {
        "name": name,
        "external_id": _get_val(record, COL["external_id"]),
        "city": _get_val(record, COL["city"]),
        "postal_code": postal_code,
        "address": _get_val(record, COL["address"]),
        "website": website_raw,
        # has_website=True ssi une URL est présente dans le CSV source.
        # None = inconnu (pas encore vérifié par l'enrichissement).
        "has_website": True if website_raw else None,
        "lead_type": _to_lead_type(_get_val(record, COL["lead_type"])),
        "star_rating": _get_val(record, COL["star_rating"]),
        "room_count": _int(COL["room_count"]),
        "capacity": _int(COL["capacity"]),
        "pitch_count": _int(COL["pitch_count"]),
        "status": LeadStatus.NEW,
        "source": "data.gouv.fr",
        "gouv_synced_at": datetime.utcnow(),
    }


def _dept_from_cp(postal_code: Optional[str]) -> Optional[str]:
    """Extrait le code département depuis un code postal."""
    if not postal_code or len(postal_code) < 2:
        return None
    # Corse : 2A/2B encodés comme 20xxx
    if postal_code.startswith("20"):
        return "2A"  # approximation
    return postal_code[:2]


class GouvDataService:
    """
    Gère les imports depuis data.gouv.fr avec checkpoint par offset de ligne.
    """

    def __init__(self):
        self.http = httpx.AsyncClient(timeout=60.0)
        CACHE_DIR.mkdir(exist_ok=True)

    async def close(self):
        await self.http.aclose()

    # ─── Création d'un job ────────────────────────────────────────────────────

    async def create_job(
        self,
        db: AsyncSession,
        lead_types: list[str],
        region: Optional[str] = None,
        department: Optional[str] = None,
        star_filter: Optional[list[str]] = None,
        dataset_slug: str = DATASET_SLUG,
        batch_size: int = 100,
    ) -> GouvImportJob:
        job = GouvImportJob(
            dataset_slug=dataset_slug,
            resource_id=RESOURCE_ID,
            lead_types_json=json.dumps(lead_types),
            region_filter=region,
            department_filter=department,
            star_filter=json.dumps(star_filter) if star_filter else None,
            batch_size=batch_size,
            status=JobStatus.PENDING,
            current_page=1,  # ici current_page = numéro du lot (1-based)
        )
        db.add(job)
        await db.commit()
        await db.refresh(job)
        logger.info(
            f"Job #{job.id} créé — types={lead_types} région={region} dept={department} étoiles={star_filter}"
        )
        return job

    # ─── Lancement / reprise ──────────────────────────────────────────────────

    async def start_job(
        self, db: AsyncSession, job_id: int
    ) -> AsyncGenerator[dict, None]:
        """
        Lance ou reprend un job. Génère des événements de progression.
        current_page = index du lot en cours (lot 1 = lignes 0-99, lot 2 = 100-199…)
        """
        job = await self._get_job(db, job_id)
        if not job:
            yield {"event": "error", "message": f"Job #{job_id} introuvable"}
            return
        if job.status == JobStatus.COMPLETED:
            yield {"event": "error", "message": "Ce job est déjà terminé"}
            return

        job.status = JobStatus.RUNNING
        job.started_at = job.started_at or datetime.utcnow()
        await db.commit()

        # ── 1. Télécharger le CSV (cache local) ───────────────────────────────
        cache_path = CACHE_DIR / f"gouv_cache_{job.id}.csv"

        if not cache_path.exists():
            yield {
                "event": "info",
                "message": "Téléchargement du fichier CSV Atout France…",
            }
            try:
                await self._download_csv_to_file(CSV_URL, cache_path)
            except Exception as e:
                job.status = JobStatus.FAILED
                job.last_error = f"Téléchargement échoué : {e}"
                await db.commit()
                yield {"event": "error", "message": job.last_error}
                return
        else:
            yield {
                "event": "info",
                "message": "Fichier CSV en cache — reprise depuis le checkpoint",
            }

        # ── 2. Charger le CSV et calculer le total ────────────────────────────
        try:
            all_records = self._read_csv(cache_path)
        except Exception as e:
            job.status = JobStatus.FAILED
            job.last_error = f"Lecture CSV échouée : {e}"
            await db.commit()
            yield {"event": "error", "message": job.last_error}
            return

        total_records = len(all_records)
        total_pages = math.ceil(total_records / job.batch_size)

        job.total_records_estimated = total_records
        job.total_pages = total_pages
        await db.commit()

        yield {
            "event": "started",
            "job_id": job.id,
            "total_records": total_records,
            "total_pages": total_pages,
            "resuming_from_page": job.current_page,
            "message": f"{total_records} établissements — reprise lot {job.current_page}/{total_pages}",
        }

        # ── 3. Boucle par lots avec checkpoint ────────────────────────────────
        batch_num = job.current_page  # on repart depuis le checkpoint

        while batch_num <= total_pages:
            # Vérifier si le job a été mis en pause entre deux lots
            await db.refresh(job)
            if job.status == JobStatus.PAUSED:
                yield {
                    "event": "paused",
                    "page": batch_num,
                    "message": "Import mis en pause",
                }
                return

            offset_start = (batch_num - 1) * job.batch_size
            offset_end = min(offset_start + job.batch_size, total_records)
            batch = all_records[offset_start:offset_end]

            if not batch:
                break

            created, skipped, errors = await self._process_batch(db, job, batch)

            # ── CHECKPOINT ────────────────────────────────────────────────────
            job.current_page = batch_num + 1
            job.total_fetched += len(batch)
            job.total_created += created
            job.total_skipped += skipped
            job.total_errors += errors
            job.last_checkpoint_at = datetime.utcnow()
            await db.commit()
            # ── FIN CHECKPOINT ────────────────────────────────────────────────

            yield {
                "event": "progress",
                "page": batch_num,
                "total_pages": total_pages,
                "progress_pct": round(batch_num / total_pages * 100, 1),
                "batch_created": created,
                "batch_skipped": skipped,
                "total_created": job.total_created,
                "total_fetched": job.total_fetched,
            }

            batch_num += 1

        # ── 4. Fin — nettoyage cache ──────────────────────────────────────────
        try:
            cache_path.unlink(missing_ok=True)
        except Exception:
            pass

        job.status = JobStatus.COMPLETED
        job.completed_at = datetime.utcnow()
        await db.commit()

        yield {
            "event": "completed",
            "job_id": job.id,
            "total_created": job.total_created,
            "total_skipped": job.total_skipped,
            "total_errors": job.total_errors,
            "message": f"Import terminé — {job.total_created} leads créés",
        }

    # ─── Traitement d'un lot ──────────────────────────────────────────────────

    async def _process_batch(
        self,
        db: AsyncSession,
        job: GouvImportJob,
        records: list[dict],
    ) -> tuple[int, int, int]:
        created = skipped = errors = 0
        wanted_types = set(job.lead_types)

        # Préparer les codes département de la région filtrée
        region_depts: Optional[set[str]] = None
        if job.region_filter and job.region_filter in REGION_DEPTS:
            region_depts = set(REGION_DEPTS[job.region_filter])

        # Préparer le filtre étoiles
        wanted_stars: Optional[set[str]] = None
        if job.star_filter:
            wanted_stars = set(json.loads(job.star_filter))

        for record in records:
            try:
                data = _parse_record(record)
                if not data:
                    skipped += 1
                    continue

                # Filtre type
                if wanted_types and data["lead_type"].value not in wanted_types:
                    skipped += 1
                    continue

                # Filtre étoiles (colonne CLASSEMENT : "1 étoile", "2 étoiles", etc.)
                if wanted_stars:
                    star = data.get("star_rating") or ""
                    # Extraire le chiffre : "3 étoiles" → "3"
                    star_num = star.split()[0] if star else ""
                    if star_num not in wanted_stars:
                        skipped += 1
                        continue

                # Filtre département direct
                if job.department_filter:
                    dept = _dept_from_cp(data.get("postal_code"))
                    if dept != job.department_filter.zfill(2):
                        skipped += 1
                        continue

                # Filtre région via les codes de département
                if region_depts:
                    dept = _dept_from_cp(data.get("postal_code"))
                    if not dept or dept not in region_depts:
                        skipped += 1
                        continue

                # Déduplication — external_id en priorité
                ext_id = data.get("external_id")
                if ext_id:
                    res = await db.execute(
                        select(Lead).where(Lead.external_id == str(ext_id))
                    )
                    if res.scalar_one_or_none():
                        skipped += 1
                        continue
                else:
                    res = await db.execute(
                        select(Lead).where(
                            Lead.name == data["name"],
                            Lead.postal_code == data.get("postal_code"),
                        )
                    )
                    if res.scalar_one_or_none():
                        skipped += 1
                        continue

                lead = Lead(**data)
                lead.update_score()
                db.add(lead)
                created += 1

            except Exception as e:
                logger.warning(f"Erreur enregistrement : {e}")
                errors += 1

        try:
            await db.commit()
        except Exception as e:
            logger.error(f"Erreur commit lot : {e}")
            await db.rollback()
            errors += created
            created = 0

        return created, skipped, errors

    # ─── I/O CSV ──────────────────────────────────────────────────────────────

    async def _download_csv_to_file(self, url: str, dest: Path) -> None:
        """Télécharge le CSV en streaming vers un fichier local."""
        logger.info(f"Téléchargement CSV depuis {url} → {dest}")
        async with self.http.stream("GET", url, follow_redirects=True) as resp:
            resp.raise_for_status()
            with open(dest, "wb") as f:
                async for chunk in resp.aiter_bytes(chunk_size=65536):
                    f.write(chunk)
        size_mb = dest.stat().st_size / 1_048_576
        logger.info(f"CSV téléchargé ({size_mb:.1f} Mo) → {dest}")

    def _read_csv(self, path: Path) -> list[dict]:
        """Lit le CSV local et retourne la liste de tous les enregistrements."""
        for encoding in ("utf-8", "utf-8-sig", "latin-1", "cp1252"):
            try:
                with open(path, newline="", encoding=encoding) as f:
                    content = f.read()
                sep = ";" if content.count(";") > content.count(",") else ","
                reader = csv.DictReader(io.StringIO(content), delimiter=sep)
                records = list(reader)
                logger.info(
                    f"CSV lu ({len(records)} lignes, encodage={encoding}, sep='{sep}')"
                )
                return records
            except UnicodeDecodeError:
                continue
        raise ValueError(f"Impossible de lire {path} (encodage inconnu)")

    # ─── Gestion des jobs ─────────────────────────────────────────────────────

    async def _get_job(self, db: AsyncSession, job_id: int) -> Optional[GouvImportJob]:
        res = await db.execute(select(GouvImportJob).where(GouvImportJob.id == job_id))
        return res.scalar_one_or_none()

    async def get_job_status(self, db: AsyncSession, job_id: int) -> Optional[dict]:
        job = await self._get_job(db, job_id)
        if not job:
            return None
        return {
            "id": job.id,
            "dataset": job.dataset_slug,
            "status": job.status,
            "lead_types": job.lead_types,
            "region": job.region_filter,
            "department": job.department_filter,
            "star_filter": json.loads(job.star_filter) if job.star_filter else None,
            "current_page": job.current_page,
            "total_pages": job.total_pages,
            "progress_pct": job.progress_pct,
            "total_fetched": job.total_fetched,
            "total_created": job.total_created,
            "total_skipped": job.total_skipped,
            "total_errors": job.total_errors,
            "last_error": job.last_error,
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "last_checkpoint_at": job.last_checkpoint_at.isoformat()
            if job.last_checkpoint_at
            else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            "can_resume": job.can_resume,
        }

    async def list_jobs(self, db: AsyncSession) -> list[dict]:
        res = await db.execute(
            select(GouvImportJob).order_by(GouvImportJob.created_at.desc())
        )
        jobs = res.scalars().all()
        return [s for job in jobs if (s := await self.get_job_status(db, job.id))]

    async def pause_job(self, db: AsyncSession, job_id: int) -> bool:
        job = await self._get_job(db, job_id)
        if not job or job.status != JobStatus.RUNNING:
            return False
        job.status = JobStatus.PAUSED
        await db.commit()
        return True

    async def search_datasets(self, query: str) -> list[dict]:
        try:
            resp = await self.http.get(
                f"{GOUV_API}/datasets/",
                params={"q": query, "page_size": 8, "sort": "reuse_count"},
            )
            resp.raise_for_status()
            return [
                {
                    "id": d["id"],
                    "slug": d.get("slug", ""),
                    "title": d.get("title", ""),
                    "url": f"https://www.data.gouv.fr/datasets/{d.get('slug', d['id'])}",
                }
                for d in resp.json().get("data", [])
            ]
        except Exception as e:
            logger.error(f"Erreur recherche datasets : {e}")
            return []
