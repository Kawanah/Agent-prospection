"""
Service d'import de fichiers CSV/Excel.
Transforme les fichiers de prospects en leads dans la base de données.
"""

import re
import unicodedata
from pathlib import Path
from typing import Optional
import pandas as pd
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.lead import Lead, LeadType
from app.schemas.lead import LeadImportRow, ImportResult


class TextNormalizer:
    """Utilitaire pour normaliser les textes."""

    @staticmethod
    def normalize_text(text: Optional[str]) -> Optional[str]:
        """
        Normalise un texte :
        - Supprime les espaces en début/fin
        - Normalise les espaces multiples
        - Gère les caractères spéciaux
        """
        if text is None or pd.isna(text):
            return None
        text = str(text).strip()
        if not text or text.lower() in ("nan", "none", "-", "n/a", ""):
            return None
        # Normaliser les espaces multiples
        text = re.sub(r"\s+", " ", text)
        return text

    @staticmethod
    def normalize_name(name: Optional[str]) -> Optional[str]:
        """
        Normalise un nom d'établissement :
        - Capitalise correctement (Title Case)
        - Gère les accents
        - Supprime les caractères spéciaux indésirables
        """
        text = TextNormalizer.normalize_text(name)
        if not text:
            return None
        # Mettre en Title Case tout en préservant les accents
        # Mais garder les acronymes en majuscules (HOTEL, SPA, etc.)
        words = text.split()
        result = []
        for word in words:
            if word.isupper() and len(word) <= 4:
                # Garder les acronymes courts en majuscules
                result.append(word)
            else:
                result.append(word.capitalize())
        return " ".join(result)

    @staticmethod
    def normalize_city(city: Optional[str]) -> Optional[str]:
        """Normalise un nom de ville."""
        text = TextNormalizer.normalize_text(city)
        if not text:
            return None
        # Les villes en majuscules
        return text.upper()

    @staticmethod
    def normalize_postal_code(code: Optional[str]) -> Optional[str]:
        """
        Normalise un code postal français :
        - Convertit en string
        - Enlève les décimales (75010.0 -> 75010)
        - Ajoute le zéro devant si nécessaire (1000 -> 01000)
        """
        if code is None or pd.isna(code):
            return None
        code_str = str(code).strip()
        # Gérer les floats (75010.0)
        if "." in code_str:
            code_str = code_str.split(".")[0]
        # Enlever tout ce qui n'est pas un chiffre
        code_str = re.sub(r"[^\d]", "", code_str)
        if not code_str:
            return None
        # Ajouter zéro devant si nécessaire
        if len(code_str) == 4:
            code_str = "0" + code_str
        # Vérifier la longueur
        if len(code_str) != 5:
            return None
        return code_str

    @staticmethod
    def normalize_phone(phone: Optional[str]) -> Optional[str]:
        """
        Normalise un numéro de téléphone français :
        - Format: 01 23 45 67 89
        """
        if phone is None or pd.isna(phone):
            return None
        # Enlever tout ce qui n'est pas un chiffre
        digits = re.sub(r"[^\d]", "", str(phone))
        # Gérer les numéros avec indicatif
        if digits.startswith("33") and len(digits) == 11:
            digits = "0" + digits[2:]
        if len(digits) != 10:
            return None
        # Formater
        return f"{digits[0:2]} {digits[2:4]} {digits[4:6]} {digits[6:8]} {digits[8:10]}"

    @staticmethod
    def normalize_email(email: Optional[str]) -> Optional[str]:
        """Normalise une adresse email."""
        text = TextNormalizer.normalize_text(email)
        if not text:
            return None
        # Email en minuscules
        text = text.lower()
        # Validation basique
        if "@" not in text or "." not in text:
            return None
        return text

    @staticmethod
    def normalize_url(url: Optional[str]) -> Optional[str]:
        """Normalise une URL."""
        text = TextNormalizer.normalize_text(url)
        if not text:
            return None
        text = text.lower()
        # Ajouter http:// si manquant
        if not text.startswith(("http://", "https://")):
            text = "https://" + text
        return text

    @staticmethod
    def remove_accents(text: str) -> str:
        """Supprime les accents d'un texte (pour la comparaison)."""
        return "".join(
            c
            for c in unicodedata.normalize("NFD", text)
            if unicodedata.category(c) != "Mn"
        )


class ImportService:
    """Service pour importer des fichiers de prospects."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.normalizer = TextNormalizer()

    async def import_file(
        self,
        file_path: str,
        skip_header_rows: int = 0,
        limit: Optional[int] = None,
        batch_id: Optional[int] = None,
    ) -> ImportResult:
        """
        Importe un fichier CSV ou Excel dans la base de données.
        Détecte automatiquement le format selon l'extension.
        """
        path = Path(file_path)

        if not path.exists():
            return ImportResult(
                success=False,
                total_rows=0,
                imported=0,
                skipped=0,
                errors=1,
                error_details=[f"Fichier non trouvé: {file_path}"],
            )

        extension = path.suffix.lower()

        if extension == ".csv":
            return await self._import_csv(file_path, skip_header_rows, limit, batch_id)
        elif extension in (".xlsx", ".xls"):
            return await self._import_excel(
                file_path, skip_header_rows, limit, batch_id
            )
        else:
            return ImportResult(
                success=False,
                total_rows=0,
                imported=0,
                skipped=0,
                errors=1,
                error_details=[
                    f"Format non supporté: {extension}. Utilisez .csv, .xlsx ou .xls"
                ],
            )

    async def _import_csv(
        self,
        file_path: str,
        skip_header_rows: int = 0,
        limit: Optional[int] = None,
        batch_id: Optional[int] = None,
    ) -> ImportResult:
        """Importe un fichier CSV."""
        logger.info(f"Import CSV: {file_path}")

        try:
            # Essayer différents encodages
            df = None
            for encoding in ["utf-8", "latin-1", "cp1252"]:
                try:
                    df = pd.read_csv(
                        file_path,
                        skiprows=skip_header_rows,
                        encoding=encoding,
                        sep=None,  # Détection automatique du séparateur
                        engine="python",
                    )
                    logger.info(f"CSV lu avec encodage: {encoding}")
                    break
                except UnicodeDecodeError:
                    continue

            if df is None:
                return ImportResult(
                    success=False,
                    total_rows=0,
                    imported=0,
                    skipped=0,
                    errors=1,
                    error_details=[
                        "Impossible de lire le fichier CSV (encodage non reconnu)"
                    ],
                )

            return await self._process_dataframe(df, limit, batch_id)

        except Exception as e:
            logger.error(f"Erreur import CSV: {e}")
            return ImportResult(
                success=False,
                total_rows=0,
                imported=0,
                skipped=0,
                errors=1,
                error_details=[f"Erreur de lecture CSV: {str(e)}"],
            )

    async def _import_excel(
        self,
        file_path: str,
        skip_header_rows: int = 0,
        limit: Optional[int] = None,
        batch_id: Optional[int] = None,
    ) -> ImportResult:
        """Importe un fichier Excel. Détecte automatiquement la ligne d'en-tête."""
        logger.info(f"Import Excel: {file_path}")

        try:
            # Essayer d'abord sans sauter de ligne
            df = pd.read_excel(file_path, skiprows=0)
            # Si la colonne attendue n'est pas là, essayer en sautant la première ligne (fichier avec titre)
            if "NOM COMMERCIAL" not in df.columns:
                df = pd.read_excel(file_path, skiprows=1)
                logger.info("En-tête détecté à la ligne 2 du fichier Excel")
            return await self._process_dataframe(df, limit, batch_id)

        except Exception as e:
            logger.error(f"Erreur import Excel: {e}")
            return ImportResult(
                success=False,
                total_rows=0,
                imported=0,
                skipped=0,
                errors=1,
                error_details=[f"Erreur de lecture Excel: {str(e)}"],
            )

    async def _process_dataframe(
        self,
        df: pd.DataFrame,
        limit: Optional[int] = None,
        batch_id: Optional[int] = None,
    ) -> ImportResult:
        """Traite un DataFrame et importe les leads."""
        total_rows = len(df)
        logger.info(
            f"DataFrame chargé: {total_rows} lignes, colonnes: {list(df.columns)}"
        )

        if limit:
            df = df.head(limit)
            logger.info(f"Limité à {limit} lignes")

        imported = 0
        skipped = 0
        errors = 0
        error_details = []

        for index, row in df.iterrows():
            try:
                row_dict = row.to_dict()

                # Vérifier que le nom commercial existe
                nom = row_dict.get("NOM COMMERCIAL")
                if pd.isna(nom) or not str(nom).strip():
                    skipped += 1
                    continue

                # Normaliser le nom avant tout
                name = self.normalizer.normalize_name(str(nom).strip())
                if not name:
                    skipped += 1
                    continue

                # Valider avec Pydantic
                try:
                    lead_data = LeadImportRow.model_validate(row_dict)
                except Exception as e:
                    errors += 1
                    error_details.append(
                        f"Ligne {index + 2}: Validation - {str(e)[:80]}"
                    )
                    continue

                # Vérifier si le lead existe déjà (déduplication)
                try:
                    existing = await self._find_existing_lead(
                        name=lead_data.nom_commercial,
                        postal_code=lead_data.code_postal,
                    )
                    if existing:
                        skipped += 1
                        continue
                except Exception as e:
                    logger.warning(f"Erreur dédup ligne {index + 2}: {e}")
                    # Continuer sans vérification de doublon plutôt que de bloquer

                # Créer le lead avec normalisation et l'insérer dans un savepoint isolé
                lead = self._create_lead_from_row(lead_data, batch_id=batch_id)
                try:
                    async with self.db.begin_nested():
                        self.db.add(lead)
                        await self.db.flush()
                    imported += 1
                except Exception as insert_err:
                    errors += 1
                    error_details.append(
                        f"Ligne {index + 2}: INSERT - {str(insert_err)[:80]}"
                    )
                    continue

                # Commit par lots de 100
                if imported % 100 == 0:
                    try:
                        await self.db.commit()
                        logger.info(f"Progression: {imported} leads importés...")
                    except Exception as commit_err:
                        logger.error(f"Erreur commit lot: {commit_err}")
                        await self.db.rollback()
                        errors += 1
                        error_details.append(
                            f"Lot ligne ~{index + 2}: commit échoué - {str(commit_err)[:80]}"
                        )

            except Exception as e:
                errors += 1
                error_details.append(f"Ligne {index + 2}: {str(e)[:80]}")

        # Commit final pour les leads en attente
        try:
            await self.db.commit()
        except Exception as e:
            logger.error(f"Erreur commit final: {e}")
            await self.db.rollback()

        logger.info(
            f"Import terminé: {imported} importés, {skipped} ignorés, {errors} erreurs"
        )

        return ImportResult(
            success=True,
            total_rows=total_rows,
            imported=imported,
            skipped=skipped,
            errors=errors,
            error_details=error_details[:20],
        )

    async def _find_existing_lead(
        self, name: str, postal_code: Optional[str]
    ) -> Optional[Lead]:
        """
        Vérifie si un lead existe déjà.
        Utilise une comparaison normalisée (sans accents, minuscules).
        """
        # Normaliser le nom pour la recherche
        normalized_name = self.normalizer.normalize_name(name)
        if not normalized_name:
            return None

        query = select(Lead).where(Lead.name == normalized_name)
        if postal_code:
            normalized_cp = self.normalizer.normalize_postal_code(postal_code)
            if normalized_cp:
                query = query.where(Lead.postal_code == normalized_cp)

        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    def _create_lead_from_row(
        self, data: LeadImportRow, batch_id: Optional[int] = None
    ) -> Lead:
        """Crée un Lead à partir d'une ligne importée, avec normalisation."""
        # Normaliser toutes les données
        name = self.normalizer.normalize_name(data.nom_commercial)
        city = self.normalizer.normalize_city(data.commune)
        postal_code = self.normalizer.normalize_postal_code(data.code_postal)
        address = self.normalizer.normalize_text(data.adresse)

        # Gérer le site web
        # None = inconnu (pas encore vérifié), True = URL connue, False = confirmé sans site (enrichissement uniquement)
        website = self.normalizer.normalize_url(data.site_internet)
        has_website = True if website else None

        lead = Lead(
            name=name,
            lead_type=data.to_lead_type(),
            # Taille de l'établissement
            capacity=data.capacite_accueil,
            room_count=data.nombre_chambres,
            pitch_count=data.nombre_emplacements,
            star_rating=data.classement,
            # Localisation
            address=address,
            city=city,
            postal_code=postal_code,
            country="France",
            website=website,
            has_website=has_website,
            source="file_import",
            batch_id=batch_id,
        )

        # Calculer le score initial
        lead.update_score()

        return lead


# Fonctions helpers pour l'API
async def import_file(
    db: AsyncSession,
    file_path: str,
    limit: Optional[int] = None,
    batch_id: Optional[int] = None,
) -> ImportResult:
    """Fonction helper pour importer un fichier (CSV ou Excel)."""
    service = ImportService(db)
    return await service.import_file(file_path, limit=limit, batch_id=batch_id)
