"""
Service d'import de fichiers CSV d'inscriptions RCS (nouvelles entreprises).

Détecte automatiquement les colonnes du CSV et crée des leads marqués
is_nouvelle_entreprise=True avec scoring RCS (0-5 pts).

Colonnes attendues (noms flexibles, détection automatique) :
- SIREN / Numéro SIREN
- Dénomination / Raison sociale / Nom
- Forme juridique
- Capital / Capital social
- Adresse / Siège social
- Code postal / CP
- Ville / Commune
- Date de création / Date d'immatriculation
- NAF / Code APE / Activité principale
- Objet social / Activité déclarée
"""

import csv
import io
from pathlib import Path
from typing import Optional

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lead import Lead, LeadType, LeadStatus
from app.models.contact import Contact, ContactRole


# Mapping flexible des colonnes CSV → champs internes
COLUMN_MAPPING = {
    "siren": [
        "siren",
        "numero_siren",
        "n_siren",
        "numéro siren",
        "n° siren",
        "numero siren",
        "siren_number",
    ],
    "name": [
        "denomination",
        "dénomination",
        "raison_sociale",
        "raison sociale",
        "nom",
        "nom commercial",
        "nom_commercial",
        "entreprise",
        "denomination_sociale",
        "dénomination sociale",
    ],
    "forme_juridique": [
        "forme_juridique",
        "forme juridique",
        "type_societe",
        "type société",
        "statut juridique",
        "forme",
    ],
    "capital": [
        "capital",
        "capital_social",
        "capital social",
        "montant_capital",
    ],
    "address": [
        "adresse",
        "siege",
        "siège",
        "siège social",
        "siege_social",
        "adresse_siege",
        "adresse siege",
    ],
    "postal_code": [
        "code_postal",
        "code postal",
        "cp",
        "codepostal",
    ],
    "city": [
        "ville",
        "commune",
        "localité",
        "localite",
    ],
    "date_creation": [
        "date_creation",
        "date de création",
        "date_immatriculation",
        "date immatriculation",
        "date de creation",
        "creation_date",
    ],
    "naf": [
        "naf",
        "code_naf",
        "code naf",
        "code_ape",
        "code ape",
        "ape",
        "activite_principale",
        "activité principale",
    ],
    "objet_social": [
        "objet_social",
        "objet social",
        "activite",
        "activité",
        "activite_declaree",
        "activité déclarée",
        "description_activite",
    ],
    "dirigeant_nom": [
        "dirigeant",
        "dirigeant_nom",
        "nom_dirigeant",
        "gérant",
        "gerant",
        "representant",
        "représentant",
    ],
    "dirigeant_prenom": [
        "prenom_dirigeant",
        "prénom_dirigeant",
        "prenom dirigeant",
        "prénom dirigeant",
        "prenom",
    ],
}


def _normalize_header(header: str) -> str:
    """Normalise un nom de colonne pour le matching."""
    return (
        header.strip()
        .lower()
        .replace("_", " ")
        .replace("-", " ")
        .replace("'", "")
        .replace("'", "")
    )


def _detect_columns(headers: list[str]) -> dict[str, int]:
    """
    Détecte la correspondance entre les colonnes du CSV et nos champs internes.
    Retourne un dict {champ_interne: index_colonne}.
    """
    mapping = {}
    normalized = [_normalize_header(h) for h in headers]

    for field, variants in COLUMN_MAPPING.items():
        for i, norm_header in enumerate(normalized):
            if norm_header in [v.lower() for v in variants]:
                mapping[field] = i
                break
            # Matching partiel pour les colonnes composites
            for variant in variants:
                if variant.lower() in norm_header or norm_header in variant.lower():
                    if field not in mapping:
                        mapping[field] = i
                        break

    return mapping


def _clean_capital(raw: str) -> Optional[int]:
    """Convertit le capital (string) en entier."""
    if not raw:
        return None
    raw = raw.strip().replace("€", "").replace(" ", "").replace(",", ".")
    try:
        return int(float(raw))
    except (ValueError, TypeError):
        return None


def _clean_postal(raw: str) -> Optional[str]:
    """Nettoie le code postal."""
    if not raw:
        return None
    raw = str(raw).strip()
    if "." in raw:
        raw = raw.split(".")[0]
    if len(raw) == 4:
        raw = "0" + raw
    return raw if len(raw) == 5 else None


def _detect_lead_type(naf: Optional[str], objet: Optional[str]) -> LeadType:
    """Déduit le type de lead à partir du NAF ou de l'objet social."""
    text = ((naf or "") + " " + (objet or "")).lower()
    if any(w in text for w in ("hotel", "hôtel", "hébergement", "5510")):
        return LeadType.HOTEL
    if any(w in text for w in ("camping", "5530", "emplacement")):
        return LeadType.CAMPING
    if any(w in text for w in ("gîte", "gite", "meublé", "5520")):
        return LeadType.GITE
    if any(w in text for w in ("chambre d'hôte", "chambre d hote")):
        return LeadType.CHAMBRE_HOTES
    if any(w in text for w in ("résidence", "residence")):
        return LeadType.RESIDENCE
    if any(
        w in text
        for w in ("activit", "loisir", "sport", "guide", "7990", "9329", "9319")
    ):
        return LeadType.ACTIVITE
    return LeadType.OTHER


DOMICILIATION_KEYWORDS = [
    "domiciliation",
    "domicilié",
    "chez",
    "c/o",
    "boîte postale",
    "boite postale",
    "bp ",
]


async def import_rcs_csv(
    db: AsyncSession,
    file_path: str,
    limit: Optional[int] = None,
    batch_id: Optional[int] = None,
) -> dict:
    """
    Importe un fichier CSV d'inscriptions RCS.
    Chaque lead est marqué is_nouvelle_entreprise=True.

    Retourne les statistiques d'import.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Fichier introuvable : {file_path}")

    # Détecter l'encoding
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-8", "latin-1", "cp1252"):
        try:
            content = raw.decode(encoding)
            break
        except (UnicodeDecodeError, UnicodeError):
            continue
    else:
        raise ValueError("Impossible de décoder le fichier CSV")

    # Détecter le séparateur
    first_line = content.split("\n")[0]
    sep = ";" if first_line.count(";") > first_line.count(",") else ","

    reader = csv.reader(io.StringIO(content), delimiter=sep)
    headers = next(reader)
    col_map = _detect_columns(headers)

    if "name" not in col_map and "siren" not in col_map:
        raise ValueError(
            "Impossible de détecter les colonnes essentielles (dénomination ou SIREN). "
            f"Colonnes trouvées : {headers}"
        )

    logger.info(
        f"Import RCS : {len(col_map)} colonnes détectées sur {len(headers)} — "
        f"{list(col_map.keys())}"
    )

    imported = 0
    skipped = 0
    errors = 0
    error_details = []

    for i, row in enumerate(reader):
        if limit and imported >= limit:
            break

        try:

            def _get(field: str) -> Optional[str]:
                idx = col_map.get(field)
                if idx is None or idx >= len(row):
                    return None
                val = row[idx].strip()
                return val if val else None

            name = _get("name")
            siren = _get("siren")

            if not name and not siren:
                skipped += 1
                continue

            # Déduplication par SIREN
            if siren:
                siren = siren.replace(" ", "")
                existing = await db.execute(select(Lead).where(Lead.siren == siren))
                if existing.scalar_one_or_none():
                    skipped += 1
                    continue
                # Fallback : chercher dans external_id
                existing2 = await db.execute(
                    select(Lead).where(Lead.external_id == siren)
                )
                if existing2.scalar_one_or_none():
                    skipped += 1
                    continue

            # Déduplication par nom + ville
            city = _get("city")
            if name and city:
                existing3 = await db.execute(
                    select(Lead).where(Lead.name == name, Lead.city == city)
                )
                if existing3.scalar_one_or_none():
                    skipped += 1
                    continue

            naf = _get("naf")
            objet = _get("objet_social")
            forme = _get("forme_juridique")
            capital = _clean_capital(_get("capital") or "")
            address = _get("address")

            # Détecter domiciliation
            is_domiciliataire = False
            if address:
                addr_lower = address.lower()
                is_domiciliataire = any(
                    kw in addr_lower for kw in DOMICILIATION_KEYWORDS
                )

            lead = Lead(
                name=name or f"Entreprise {siren}",
                lead_type=_detect_lead_type(naf, objet),
                address=address,
                city=city,
                postal_code=_clean_postal(_get("postal_code") or ""),
                country="France",
                source="rcs_import",
                is_nouvelle_entreprise=True,
                siren=siren,
                external_id=siren,
                objet_social=objet,
                capital=capital,
                forme_juridique=forme,
                domiciliation=address if is_domiciliataire else None,
                is_domiciliataire=is_domiciliataire or None,
                status=LeadStatus.NEW,
                batch_id=batch_id,
            )
            lead.update_rcs_score()
            db.add(lead)
            await db.flush()

            # Créer le contact dirigeant s'il y a des infos
            dirigeant_nom = _get("dirigeant_nom")
            dirigeant_prenom = _get("dirigeant_prenom")
            if dirigeant_nom or dirigeant_prenom:
                contact = Contact(
                    lead_id=lead.id,
                    first_name=dirigeant_prenom,
                    last_name=dirigeant_nom,
                    full_name=" ".join(filter(None, [dirigeant_prenom, dirigeant_nom])),
                    role=ContactRole.OWNER,
                    source="rcs_import",
                )
                db.add(contact)

            imported += 1

        except Exception as e:
            errors += 1
            if len(error_details) < 10:
                error_details.append(f"Ligne {i + 2}: {str(e)[:100]}")
            logger.warning(f"Import RCS ligne {i + 2}: {e}")

    await db.commit()

    logger.info(
        f"Import RCS terminé : {imported} importés, {skipped} ignorés, {errors} erreurs"
    )

    return {
        "success": errors == 0,
        "total_rows": imported + skipped + errors,
        "imported": imported,
        "skipped": skipped,
        "errors": errors,
        "error_details": error_details,
    }
