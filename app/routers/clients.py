from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import exiger_roles, get_utilisateur_connecte
from app.models import Utilisateur
from app.schemas.client import ClientCreation, ClientLecture, ClientModification
from app.schemas.commande import CommandeResume, ResumeClient
from app.schemas.pagination import Page
from app.services import clients as service
from app.services import commandes as service_commandes

router = APIRouter(prefix="/clients", tags=["Clients"])


@router.post("", response_model=ClientLecture, status_code=201)
def creer(
    donnees: ClientCreation,
    db: Session = Depends(get_db),
    utilisateur: Utilisateur = Depends(get_utilisateur_connecte),
):
    """Crée un client (tous les rôles). 409 si le téléphone existe déjà."""
    client = service.creer_client(db, donnees)
    db.commit()
    return client


@router.get("", response_model=Page[ClientLecture])
def lister(
    q: str | None = Query(default=None, min_length=2, description="Recherche nom, prénom, téléphone"),
    genre: Literal["homme", "femme", "enfant"] | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    utilisateur: Utilisateur = Depends(get_utilisateur_connecte),
):
    """Liste paginée, triée par nom puis prénom."""
    clients, total = service.lister_clients(db, q, genre, limit, offset)
    return Page[ClientLecture](items=clients, total=total, limit=limit, offset=offset)


@router.get("/{client_id}", response_model=ClientLecture)
def detail(
    client_id: int,
    db: Session = Depends(get_db),
    utilisateur: Utilisateur = Depends(get_utilisateur_connecte),
):
    """Fiche d'un client."""
    return service.lire_client(db, client_id)


@router.get("/{client_id}/commandes", response_model=Page[CommandeResume])
def commandes_du_client(
    client_id: int,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    utilisateur: Utilisateur = Depends(get_utilisateur_connecte),
):
    """Commandes d'un client, paginées, la plus récente d'abord."""
    commandes, total = service_commandes.lister_commandes_du_client(db, client_id, limit, offset)
    items = []
    for commande in commandes:
        items.append(service_commandes.construire_resume(commande))
    return Page[CommandeResume](items=items, total=total, limit=limit, offset=offset)


@router.get("/{client_id}/resume", response_model=ResumeClient)
def resume_du_client(
    client_id: int,
    db: Session = Depends(get_db),
    utilisateur: Utilisateur = Depends(get_utilisateur_connecte),
):
    """Résumé d'un client (commandes annulées exclues)."""
    return service_commandes.resume_du_client(db, client_id)


@router.patch("/{client_id}", response_model=ClientLecture)
def modifier(
    client_id: int,
    donnees: ClientModification,
    db: Session = Depends(get_db),
    utilisateur: Utilisateur = Depends(get_utilisateur_connecte),
):
    """Modification partielle d'un client."""
    client = service.modifier_client(db, client_id, donnees)
    db.commit()
    return client


@router.delete("/{client_id}", status_code=204)
def supprimer(
    client_id: int,
    db: Session = Depends(get_db),
    admin: Utilisateur = Depends(exiger_roles([])),
):
    """Supprime un client (admin). 409 s'il a des commandes (RG4)."""
    service.supprimer_client(db, client_id)
    db.commit()
