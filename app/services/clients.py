from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import Client, Commande
from app.schemas.client import ClientCreation, ClientModification
from app.services.telephone import normaliser_telephone


def verifier_telephone_libre(db: Session, telephone: str, client_id_exclu: int | None = None) -> None:
    """RG1 : le téléphone doit être unique (409 sinon)."""
    requete = select(Client).where(Client.telephone == telephone)
    if client_id_exclu is not None:
        requete = requete.where(Client.id != client_id_exclu)
    if db.scalars(requete).first() is not None:
        raise HTTPException(
            status_code=409, detail="Un client avec ce numéro de téléphone existe déjà"
        )


def creer_client(db: Session, donnees: ClientCreation) -> Client:
    verifier_telephone_libre(db, donnees.telephone)
    client = Client(
        nom=donnees.nom,
        prenom=donnees.prenom,
        telephone=donnees.telephone,
        email=donnees.email,
        adresse=donnees.adresse,
        genre=donnees.genre,
        notes=donnees.notes,
    )
    db.add(client)
    db.flush()
    db.refresh(client)
    return client


def lire_client(db: Session, client_id: int) -> Client:
    client = db.get(Client, client_id)
    if client is None:
        raise HTTPException(status_code=404, detail="Client introuvable")
    return client


def lister_clients(
    db: Session, q: str | None, genre: str | None, limit: int, offset: int
) -> tuple[list[Client], int]:
    requete = select(Client)

    if q is not None:
        motif = "%" + q.strip() + "%"
        motif_telephone = "%" + normaliser_telephone(q) + "%"
        requete = requete.where(
            or_(
                Client.nom.ilike(motif),
                Client.prenom.ilike(motif),
                Client.telephone.ilike(motif_telephone),
            )
        )
    if genre is not None:
        requete = requete.where(Client.genre == genre)

    total = db.scalar(select(func.count()).select_from(requete.subquery()))

    requete = requete.order_by(Client.nom, Client.prenom, Client.id).limit(limit).offset(offset)
    clients = list(db.scalars(requete).all())
    return clients, total


def modifier_client(db: Session, client_id: int, donnees: ClientModification) -> Client:
    client = lire_client(db, client_id)
    changements = donnees.model_dump(exclude_unset=True)

    if "telephone" in changements:
        # Garder son propre numéro n'est pas un doublon
        verifier_telephone_libre(db, changements["telephone"], client_id_exclu=client.id)

    for champ, valeur in changements.items():
        setattr(client, champ, valeur)

    db.flush()
    db.refresh(client)
    return client


def supprimer_client(db: Session, client_id: int) -> None:
    client = lire_client(db, client_id)

    # RG4 : un client qui a des commandes ne peut pas être supprimé
    nombre_commandes = db.scalar(
        select(func.count()).select_from(Commande).where(Commande.client_id == client.id)
    )
    if nombre_commandes > 0:
        raise HTTPException(
            status_code=409,
            detail="Ce client a des commandes : impossible de le supprimer",
        )

    # Les mesures du client sont supprimées par la base (ON DELETE CASCADE)
    db.delete(client)
    db.flush()
