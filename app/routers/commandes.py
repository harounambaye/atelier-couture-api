from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import exiger_roles, get_utilisateur_connecte
from app.models import Utilisateur
from app.schemas.commande import (
    CommandeCreation,
    CommandeDetail,
    CommandeModification,
    CommandeResume,
    LigneCommandeCreation,
)
from app.schemas.pagination import Page
from app.services import commandes as service

router = APIRouter(prefix="/commandes", tags=["Commandes"])

# L'accueil gère les commandes (l'admin passe toujours)
SEULEMENT_ACCUEIL = exiger_roles(["accueil"])


@router.post("", response_model=CommandeDetail, status_code=201)
def creer(
    donnees: CommandeCreation,
    db: Session = Depends(get_db),
    utilisateur: Utilisateur = Depends(SEULEMENT_ACCUEIL),
):
    """Crée une commande (accueil) : numéro, montants et date prévue calculés."""
    commande = service.creer_commande(db, donnees, utilisateur)
    db.commit()
    return service.construire_detail(commande)


@router.get("", response_model=Page[CommandeResume])
def lister(
    statut: Literal[
        "en_attente", "en_coupe", "en_couture", "essayage",
        "retouches", "terminee", "livree", "annulee",
    ] | None = None,
    client_id: int | None = None,
    en_retard: bool | None = None,
    date_min: date | None = None,
    date_max: date | None = None,
    numero: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    utilisateur: Utilisateur = Depends(get_utilisateur_connecte),
):
    """Liste paginée, la plus récente d'abord, avec filtres."""
    commandes, total = service.lister_commandes(
        db, statut, client_id, en_retard, date_min, date_max, numero, limit, offset
    )
    items = []
    for commande in commandes:
        items.append(service.construire_resume(commande))
    return Page[CommandeResume](items=items, total=total, limit=limit, offset=offset)


@router.get("/{commande_id}", response_model=CommandeDetail)
def detail(
    commande_id: int,
    db: Session = Depends(get_db),
    utilisateur: Utilisateur = Depends(get_utilisateur_connecte),
):
    """Détail complet : lignes, paiements, livraison, solde."""
    return service.construire_detail(service.lire_commande(db, commande_id))


@router.patch("/{commande_id}", response_model=CommandeDetail)
def modifier(
    commande_id: int,
    donnees: CommandeModification,
    db: Session = Depends(get_db),
    utilisateur: Utilisateur = Depends(SEULEMENT_ACCUEIL),
):
    """Modifie mesure, date prévue, remise ou notes (accueil)."""
    commande = service.modifier_commande(db, commande_id, donnees)
    db.commit()
    return service.construire_detail(commande)


@router.post("/{commande_id}/lignes", response_model=CommandeDetail, status_code=201)
def ajouter_ligne(
    commande_id: int,
    donnees: LigneCommandeCreation,
    db: Session = Depends(get_db),
    utilisateur: Utilisateur = Depends(SEULEMENT_ACCUEIL),
):
    """Ajoute une ligne à une commande « en_attente » (accueil)."""
    commande = service.ajouter_ligne(db, commande_id, donnees)
    db.commit()
    return service.construire_detail(commande)


@router.delete("/{commande_id}/lignes/{ligne_id}", response_model=CommandeDetail)
def retirer_ligne(
    commande_id: int,
    ligne_id: int,
    db: Session = Depends(get_db),
    utilisateur: Utilisateur = Depends(SEULEMENT_ACCUEIL),
):
    """Retire une ligne d'une commande « en_attente » (accueil)."""
    commande = service.retirer_ligne(db, commande_id, ligne_id)
    db.commit()
    return service.construire_detail(commande)
