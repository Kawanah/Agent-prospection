"""
Endpoint d'authentification — génère un token JWT.
Route publique : POST /api/auth/login
"""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.auth import create_access_token, get_current_user, verify_password
from app.config import get_settings

router = APIRouter()
settings = get_settings()
limiter = Limiter(key_func=get_remote_address)


@router.post("/login")
@limiter.limit("10/minute")
async def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Authentification admin.
    Retourne un token JWT Bearer valable 24h.

    Paramètres (form-data) :
    - username : nom d'admin (défaut : admin)
    - password : mot de passe en clair
    """
    # Vérifier le nom d'utilisateur
    if form_data.username != settings.admin_username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Identifiants incorrects",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Cas premier démarrage : aucun hash configuré → refuser
    if not settings.admin_password_hash:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Authentification non configurée. "
                "Définissez ADMIN_PASSWORD_HASH dans votre .env. "
                'Générez un hash : python -c "from passlib.context import CryptContext; '
                "print(CryptContext(schemes=['bcrypt']).hash('votre-mdp'))\""
            ),
        )

    # Vérifier le mot de passe
    if not verify_password(form_data.password, settings.admin_password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Identifiants incorrects",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(username=form_data.username)
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": settings.jwt_expire_minutes * 60,
    }


@router.get("/me")
async def get_me(username: str = Depends(get_current_user)):
    """Retourne l'utilisateur authentifié (utile pour vérifier la validité du token)."""
    return {"username": username, "role": "admin"}
