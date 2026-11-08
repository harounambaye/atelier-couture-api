from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.dependencies import get_utilisateur_connecte
from app.models import Utilisateur
from app.schemas.auth import Jeton
from app.schemas.utilisateur import UtilisateurLecture
from app.security import creer_jeton
from app.services import auth as service_auth

router = APIRouter(prefix="/auth", tags=["Authentification"])


@router.post("/login", response_model=Jeton)
def login(
    formulaire: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """Connexion par e-mail ou numéro de téléphone (champ username) et mot de passe."""
    utilisateur = service_auth.authentifier(db, formulaire.username, formulaire.password)
    jeton = creer_jeton(utilisateur.id)
    return Jeton(
        access_token=jeton,
        expires_in=settings.access_token_expire_minutes * 60,
    )


@router.get("/me", response_model=UtilisateurLecture)
def me(utilisateur: Utilisateur = Depends(get_utilisateur_connecte)):
    """Profil de l'utilisateur connecté."""
    return utilisateur