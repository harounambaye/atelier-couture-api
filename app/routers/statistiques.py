from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import exiger_roles
from app.models import Utilisateur
from app.schemas.commande import CommandeResume
from app.schemas.pagination import Page
from app.schemas.statistiques import (
    ChiffreAffaires,
    StatistiqueClient,
    StatistiqueTypeVetement,
    TableauDeBord,
)
from app.services import commandes as service_commandes
from app.services import statistiques as service

router = APIRouter(prefix="/statistiques", tags=["Statistiques"])

# Les statistiques sont réservées à l'administrateur
SEULEMENT_ADMIN = exiger_roles([])


@router.get("/tableau-de-bord", response_model=TableauDeBord)
def tableau_de_bord(
    db: Session = Depends(get_db),
    admin: Utilisateur = Depends(SEULEMENT_ADMIN),
):
    """Vue d'ensemble : mois courant, soldes, commandes par statut, retards."""
    return service.tableau_de_bord(db)


@router.get("/chiffre-affaires", response_model=ChiffreAffaires)
def chiffre_affaires(
    granularite: Literal["jour", "mois"] = "jour",
    date_debut: date | None = None,
    date_fin: date | None = None,
    db: Session = Depends(get_db),
    admin: Utilisateur = Depends(SEULEMENT_ADMIN),
):
    """Chiffre d'affaires et encaissements par jour ou par mois."""
    return service.chiffre_affaires(db, granularite, date_debut, date_fin)


@router.get("/types-vetement", response_model=list[StatistiqueTypeVetement])
def types_vetement(
    date_debut: date | None = None,
    date_fin: date | None = None,
    db: Session = Depends(get_db),
    admin: Utilisateur = Depends(SEULEMENT_ADMIN),
):
    """Quantités vendues et chiffre d'affaires par type de vêtement."""
    return service.types_vetement(db, date_debut, date_fin)


@router.get("/top-clients", response_model=list[StatistiqueClient])
def top_clients(
    limite: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db),
    admin: Utilisateur = Depends(SEULEMENT_ADMIN),
):
    """Meilleurs clients par chiffre d'affaires."""
    return service.top_clients(db, limite)


@router.get("/impayes", response_model=Page[CommandeResume])
def impayes(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    admin: Utilisateur = Depends(SEULEMENT_ADMIN),
):
    """Commandes non soldées, les plus urgentes d'abord."""
    commandes, total = service.lister_impayes(db, limit, offset)
    items = []
    for commande in commandes:
        items.append(service_commandes.construire_resume(commande))
    return Page[CommandeResume](items=items, total=total, limit=limit, offset=offset)
