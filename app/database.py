"""
Configuration de la base de données SQLAlchemy.
"""

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

settings = get_settings()

# Créer le moteur de base de données asynchrone
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,  # Log les requêtes SQL en mode debug
)

# Créer la factory de sessions
async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Classe de base pour tous les modèles SQLAlchemy."""

    pass


async def get_db() -> AsyncSession:
    """
    Dépendance FastAPI pour obtenir une session de base de données.
    Usage: db: AsyncSession = Depends(get_db)
    """
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db():
    """Initialise la base de données (crée les tables + migrations)."""
    from sqlalchemy import text

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Migration : ajouter les colonnes manquantes (SQLite ne supporte pas IF NOT EXISTS sur ALTER)
        result = await conn.execute(text("PRAGMA table_info(leads)"))
        columns = [row[1] for row in result.fetchall()]
        if "batch_id" not in columns:
            await conn.execute(text("ALTER TABLE leads ADD COLUMN batch_id INTEGER"))

        # Migration : colonnes Nouvelles Entreprises (RCS/BODACC)
        new_lead_cols = [
            ("is_nouvelle_entreprise", "BOOLEAN DEFAULT 0"),
            ("siren", "VARCHAR(20)"),
            ("objet_social", "TEXT"),
            ("capital", "INTEGER"),
            ("forme_juridique", "VARCHAR(50)"),
            ("domiciliation", "VARCHAR(500)"),
            ("is_domiciliataire", "BOOLEAN"),
            ("bodacc_activite", "TEXT"),
            ("bodacc_publication_date", "DATE"),
            ("rcs_score", "INTEGER"),
        ]
        for col_name, col_type in new_lead_cols:
            if col_name not in columns:
                await conn.execute(
                    text(f"ALTER TABLE leads ADD COLUMN {col_name} {col_type}")
                )

        # Migration : table contacts — date_naissance
        result2 = await conn.execute(text("PRAGMA table_info(contacts)"))
        contact_columns = [row[1] for row in result2.fetchall()]
        if "date_naissance" not in contact_columns:
            await conn.execute(
                text("ALTER TABLE contacts ADD COLUMN date_naissance DATE")
            )
