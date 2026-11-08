from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import exiger_roles
from app.models import Utilisateur
from app.schemas.utilisateur import (
    UtilisateurCreation,
    UtilisateurLecture,
    UtilisateurModification,
)
from app.services import utilisateurs as service

router = APIRouter(prefix="/utilisateurs", tags=["Utilisateurs"])

# Liste vide = réservé à l'administrateur (l'admin passe toujours)
SEULEMENT_ADMIN = exiger_roles([])


@router.post("", response_model=UtilisateurLecture, status_code=201)
def creer(
    donnees: UtilisateurCreation,
    db: Session = Depends(get_db),
    admin: Utilisateur = Depends(SEULEMENT_ADMIN),
):
    """Crée un compte (admin)."""
    utilisateur = service.creer_utilisateur(db, donnees)
    db.commit()
    return utilisateur


@router.get("", response_model=list[UtilisateurLecture])
def lister(
    db: Session = Depends(get_db),
    admin: Utilisateur = Depends(SEULEMENT_ADMIN),
):
    """Liste des comptes, triés par nom (admin)."""
    return service.lister_utilisateurs(db)


@router.get("/{utilisateur_id}", response_model=UtilisateurLecture)
def detail(
    utilisateur_id: int,
    db: Session = Depends(get_db),
    admin: Utilisateur = Depends(SEULEMENT_ADMIN),
):
    """Détail d'un compte (admin)."""
    return service.lire_utilisateur(db, utilisateur_id)


@router.patch("/{utilisateur_id}", response_model=UtilisateurLecture)
def modifier(
    utilisateur_id: int,
    donnees: UtilisateurModification,
    db: Session = Depends(get_db),
    admin: Utilisateur = Depends(SEULEMENT_ADMIN),
):
    """Modifie nom, rôle, actif ou mot de passe (admin). RG24."""
    utilisateur = service.modifier_utilisateur(db, utilisateur_id, donnees, admin)
    db.commit()
    return utilisateur
