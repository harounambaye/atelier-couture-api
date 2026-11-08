from datetime import date

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Commande, Utilisateur
from app.models.mesure import CHAMPS_MESURES, Mesure
from app.schemas.mesure import MesureCreation, MesureModification
from app.services.clients import lire_client


def lire_mesure(db: Session, mesure_id: int) -> Mesure:
    mesure = db.get(Mesure, mesure_id)
    if mesure is None:
        raise HTTPException(status_code=404, detail="Prise de mesures introuvable")
    return mesure


def creer_mesure(
    db: Session, client_id: int, donnees: MesureCreation, tailleur: Utilisateur
) -> Mesure:
    client = lire_client(db, client_id)  # 404 si le client n'existe pas

    date_prise = donnees.date_prise
    if date_prise is None:
        date_prise = date.today()

    mesure = Mesure(
        client_id=client.id,
        date_prise=date_prise,
        prise_par_id=tailleur.id,
        notes=donnees.notes,
    )
    for champ in CHAMPS_MESURES:
        setattr(mesure, champ, getattr(donnees, champ))

    db.add(mesure)
    db.flush()
    return mesure


def historique_mesures(db: Session, client_id: int) -> list[Mesure]:
    """RG3 : toutes les prises sont conservées, la plus récente d'abord."""
    lire_client(db, client_id)
    requete = (
        select(Mesure)
        .where(Mesure.client_id == client_id)
        .order_by(Mesure.date_prise.desc(), Mesure.id.desc())
    )
    return list(db.scalars(requete).all())


def trouver_dernieres_mesures(db: Session, client_id: int) -> Mesure | None:
    """Prise de date la plus récente (RG3), ou None si le client n'en a pas."""
    requete = (
        select(Mesure)
        .where(Mesure.client_id == client_id)
        .order_by(Mesure.date_prise.desc(), Mesure.id.desc())
        .limit(1)
    )
    return db.scalars(requete).first()


def lire_dernieres_mesures(db: Session, client_id: int) -> Mesure:
    lire_client(db, client_id)
    mesure = trouver_dernieres_mesures(db, client_id)
    if mesure is None:
        raise HTTPException(status_code=404, detail="Ce client n'a aucune prise de mesures")
    return mesure


def modifier_mesure(db: Session, mesure_id: int, donnees: MesureModification) -> Mesure:
    mesure = lire_mesure(db, mesure_id)
    changements = donnees.model_dump(exclude_unset=True)

    for champ, valeur in changements.items():
        # La date de prise ne peut pas être vidée
        if champ == "date_prise" and valeur is None:
            continue
        setattr(mesure, champ, valeur)

    # RG2 : la correction ne doit pas supprimer toutes les mesures
    il_reste_une_mesure = False
    for champ in CHAMPS_MESURES:
        if getattr(mesure, champ) is not None:
            il_reste_une_mesure = True
    if not il_reste_une_mesure:
        db.rollback()
        raise HTTPException(
            status_code=422,
            detail="Une prise de mesures doit contenir au moins une mesure",
        )

    db.flush()
    return mesure


def supprimer_mesure(db: Session, mesure_id: int) -> None:
    mesure = lire_mesure(db, mesure_id)

    # RG4 : une prise utilisée par une commande ne peut pas être supprimée
    nombre_commandes = db.scalar(
        select(func.count()).select_from(Commande).where(Commande.mesure_id == mesure.id)
    )
    if nombre_commandes > 0:
        raise HTTPException(
            status_code=409,
            detail="Ces mesures sont utilisées par une commande : impossible de les supprimer",
        )

    db.delete(mesure)
    db.flush()
