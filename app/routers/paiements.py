from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import exiger_roles, get_utilisateur_connecte
from app.models import Utilisateur
from app.schemas.paiement import PaiementCreation, PaiementLecture
from app.services import paiements as service

router = APIRouter(tags=["Paiements"])


@router.post(
    "/commandes/{commande_id}/paiements", response_model=PaiementLecture, status_code=201
)
def encaisser(
    commande_id: int,
    donnees: PaiementCreation,
    db: Session = Depends(get_db),
    utilisateur: Utilisateur = Depends(exiger_roles(["accueil"])),
):
    """Encaisse un paiement (accueil). RG16."""
    paiement = service.enregistrer_paiement(db, commande_id, donnees, utilisateur)
    db.commit()
    return paiement


@router.get("/commandes/{commande_id}/paiements", response_model=list[PaiementLecture])
def lister(
    commande_id: int,
    db: Session = Depends(get_db),
    utilisateur: Utilisateur = Depends(get_utilisateur_connecte),
):
    """Paiements d'une commande, dans l'ordre de saisie."""
    return service.lister_paiements(db, commande_id)


@router.delete("/paiements/{paiement_id}", status_code=204)
def annuler(
    paiement_id: int,
    db: Session = Depends(get_db),
    admin: Utilisateur = Depends(exiger_roles([])),
):
    """Annule un paiement (admin). RG17 : le payé et le solde sont recalculés."""
    service.annuler_paiement(db, paiement_id)
    db.commit()
