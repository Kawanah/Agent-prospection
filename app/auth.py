"""
Authentification JWT pour l'API Kawanah Tourisme.
- Token Bearer (OAuth2)
- Admin unique configuré via .env
- Expiration configurable (défaut : 24h)
"""

from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import get_settings

settings = get_settings()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


# ── Mots de passe ─────────────────────────────────────────────────────────────


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


# ── Tokens JWT ────────────────────────────────────────────────────────────────


def create_access_token(username: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": username, "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


# ── Dépendance FastAPI ────────────────────────────────────────────────────────


async def get_current_user(token: str = Depends(oauth2_scheme)) -> str:
    """
    Dépendance à injecter dans les routes protégées.
    Vérifie le token Bearer et retourne le nom d'utilisateur.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Non authentifié. Connectez-vous pour accéder à cette ressource.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token, settings.secret_key, algorithms=[settings.jwt_algorithm]
        )
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    if username != settings.admin_username:
        raise credentials_exception

    return username
