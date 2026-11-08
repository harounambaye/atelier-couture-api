from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import exiger_roles, get_utilisateur_connecte
from app.models import Utilisateur
from app.schemas.type_vetement import (
    TypeVetementCreation,
    TypeVetementLecture,
    TypeVetementModification,
)
from app.services import catalogue as service

router = APIRouter(prefix="/catalogue", tags=["Catalogue"])


@router.post("", response_model=TypeVetementLecture, status_code=201)
def creer(
    donnees: TypeVetementCreation,
    db: Session = Depends(get_db),
    admin: Utilisateur = Depends(exiger_roles([])),
):
    """Ajoute une prestation (admin). 409 si le nom existe."""
    type_vetement = service.creer_type_vetement(db, donnees)
    db.commit()
    return type_vetement


@router.get("", response_model=list[TypeVetementLecture])
def lister(
    actifs_seulement: bool = True,
    db: Session = Depends(get_db),
    utilisateur: Utilisateur = Depends(get_utilisateur_connecte),
):
    """Catalogue trié par nom ; prestations actives seulement par défaut."""
    return service.lister_types_vetement(db, actifs_seulement)


@router.get("/{type_id}", response_model=TypeVetementLecture)
def detail(
    type_id: int,
    db: Session = Depends(get_db),
    utilisateur: Utilisateur = Depends(get_utilisateur_connecte),
):
    """Détail d'une prestation."""
    return service.lire_type_vetement(db, type_id)


@router.patch("/{type_id}", response_model=TypeVetementLecture)
def modifier(
    type_id: int,
    donnees: TypeVetementModification,
    db: Session = Depends(get_db),
    admin: Utilisateur = Depends(exiger_roles([])),
):
    """Modifie prix, délai, nom ou actif (admin)."""
    type_vetement = service.modifier_type_vetement(db, type_id, donnees)
    db.commit()
    return type_vetement
