from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import exiger_roles, get_utilisateur_connecte
from app.models import Utilisateur
from app.schemas.commande import CommandeDetail
from app.schemas.livraison import (
    ConfirmationLivraison,
    LivraisonLecture,
    LivraisonPlanification,
    LivraisonTournee,
)
from app.services import commandes as service_commandes
from app.services import livraisons as service

router = APIRouter(tags=["Livraisons"])

# L'accueil planifie et confirme les livraisons (l'admin passe toujours)
SEULEMENT_ACCUEIL = exiger_roles(["accueil"])


@router.put("/commandes/{commande_id}/livraison", response_model=LivraisonLecture)
def planifier(
    commande_id: int,
    donnees: LivraisonPlanification,
    db: Session = Depends(get_db),
    utilisateur: Utilisateur = Depends(SEULEMENT_ACCUEIL),
):
    """Planifie ou replanifie la livraison (accueil). RG18."""
    livraison = service.planifier_livraison(db, commande_id, donnees)
    db.commit()
    return livraison


@router.get("/commandes/{commande_id}/livraison", response_model=LivraisonLecture)
def lire(
    commande_id: int,
    db: Session = Depends(get_db),
    utilisateur: Utilisateur = Depends(get_utilisateur_connecte),
):
    """Livraison d'une commande (404 s'il n'y en a pas)."""
    return service.lire_livraison(db, commande_id)


@router.post("/commandes/{commande_id}/livraison/confirmer", response_model=CommandeDetail)
def confirmer(
    commande_id: int,
    donnees: ConfirmationLivraison | None = None,
    db: Session = Depends(get_db),
    utilisateur: Utilisateur = Depends(SEULEMENT_ACCUEIL),
):
    """Confirme la livraison (accueil). RG19-RG20 ; renvoie la commande."""
    commande = service.confirmer_livraison(db, commande_id, donnees, utilisateur)
    db.commit()
    return service_commandes.construire_detail(commande)


@router.get("/livraisons", response_model=list[LivraisonTournee])
def tournee(
    statut: Literal["planifiee", "livree"] | None = None,
    date_min: date | None = None,
    date_max: date | None = None,
    db: Session = Depends(get_db),
    utilisateur: Utilisateur = Depends(get_utilisateur_connecte),
):
    """Liste de tournée triée par date prévue."""
    return service.lister_livraisons(db, statut, date_min, date_max)
