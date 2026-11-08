from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Utilisateur
from app.security import lire_jeton

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


def erreur_401(message: str) -> HTTPException:
    return HTTPException(
        status_code=401,
        detail=message,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_utilisateur_connecte(
    jeton: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> Utilisateur:
    if jeton is None:
        raise erreur_401("Authentification requise")

    utilisateur_id = lire_jeton(jeton)
    if utilisateur_id is None:
        raise erreur_401("Jeton invalide ou expiré")

    # RG22 : on relit le compte en base à chaque requête
    utilisateur = db.get(Utilisateur, utilisateur_id)
    if utilisateur is None or not utilisateur.actif:
        raise erreur_401("Compte introuvable ou désactivé")

    return utilisateur


def exiger_roles(roles_autorises: list[str]):
    def verifier_role(
        utilisateur: Utilisateur = Depends(get_utilisateur_connecte),
    ) -> Utilisateur:
        # L'administrateur est autorisé à tout faire
        if utilisateur.role == "admin":
            return utilisateur
        if utilisateur.role not in roles_autorises:
            raise HTTPException(status_code=403, detail="Accès refusé : rôle insuffisant")
        return utilisateur

    return verifier_role