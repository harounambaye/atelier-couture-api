from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import exiger_roles, get_utilisateur_connecte
from app.models import Utilisateur
from app.schemas.mesure import MesureCreation, MesureLecture, MesureModification
from app.services import mesures as service

router = APIRouter(tags=["Mesures"])

# Le tailleur prend et corrige les mesures (l'admin passe toujours)
SEULEMENT_TAILLEUR = exiger_roles(["tailleur"])


@router.post("/clients/{client_id}/mesures", response_model=MesureLecture, status_code=201)
def creer(
    client_id: int,
    donnees: MesureCreation,
    db: Session = Depends(get_db),
    tailleur: Utilisateur = Depends(SEULEMENT_TAILLEUR),
):
    """Enregistre une prise de mesures (tailleur). RG2."""
    mesure = service.creer_mesure(db, client_id, donnees, tailleur)
    db.commit()
    return mesure


@router.get("/clients/{client_id}/mesures", response_model=list[MesureLecture])
def historique(
    client_id: int,
    db: Session = Depends(get_db),
    utilisateur: Utilisateur = Depends(get_utilisateur_connecte),
):
    """Historique des prises, la plus récente d'abord."""
    return service.historique_mesures(db, client_id)


@router.get("/clients/{client_id}/mesures/derniere", response_model=MesureLecture)
def derniere(
    client_id: int,
    db: Session = Depends(get_db),
    utilisateur: Utilisateur = Depends(get_utilisateur_connecte),
):
    """Dernière prise de mesures du client (404 s'il n'en a aucune)."""
    return service.lire_dernieres_mesures(db, client_id)


@router.get("/mesures/{mesure_id}", response_model=MesureLecture)
def detail(
    mesure_id: int,
    db: Session = Depends(get_db),
    utilisateur: Utilisateur = Depends(get_utilisateur_connecte),
):
    """Une prise de mesures."""
    return service.lire_mesure(db, mesure_id)


@router.patch("/mesures/{mesure_id}", response_model=MesureLecture)
def modifier(
    mesure_id: int,
    donnees: MesureModification,
    db: Session = Depends(get_db),
    tailleur: Utilisateur = Depends(SEULEMENT_TAILLEUR),
):
    """Corrige une prise de mesures (tailleur)."""
    mesure = service.modifier_mesure(db, mesure_id, donnees)
    db.commit()
    return mesure


@router.delete("/mesures/{mesure_id}", status_code=204)
def supprimer(
    mesure_id: int,
    db: Session = Depends(get_db),
    tailleur: Utilisateur = Depends(SEULEMENT_TAILLEUR),
):
    """Supprime une prise de mesures (tailleur). 409 si une commande l'utilise (RG4)."""
    service.supprimer_mesure(db, mesure_id)
    db.commit()
