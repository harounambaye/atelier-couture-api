from datetime import date

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import Commande, Paiement, Utilisateur
from app.schemas.paiement import PaiementCreation
from app.services.commandes import calculer_solde, lire_commande, recalculer_montants


def enregistrer_paiement(
    db: Session, commande_id: int, donnees: PaiementCreation, utilisateur: Utilisateur
) -> Paiement:
    commande = lire_commande(db, commande_id)

    # RG16 : pas de paiement sur une commande annulée
    if commande.statut == "annulee":
        raise HTTPException(
            status_code=409, detail="Impossible d'encaisser un paiement sur une commande annulée"
        )

    # RG16 : pas de date future
    date_paiement = donnees.date_paiement
    if date_paiement is None:
        date_paiement = date.today()
    if date_paiement > date.today():
        raise HTTPException(
            status_code=422, detail="La date de paiement ne peut pas être dans le futur"
        )

    # RG16 : le montant ne peut pas dépasser le solde restant
    solde = calculer_solde(commande)
    if donnees.montant > solde:
        raise HTTPException(
            status_code=409,
            detail="Le montant (" + str(donnees.montant) + " FCFA) dépasse le solde restant ("
            + str(solde) + " FCFA)",
        )

    paiement = Paiement(
        commande_id=commande.id,
        montant=donnees.montant,
        mode=donnees.mode,
        reference=donnees.reference,
        date_paiement=date_paiement,
        enregistre_par_id=utilisateur.id,
    )
    commande.paiements.append(paiement)
    recalculer_montants(commande)  # RG7 : payé = somme des paiements
    db.flush()
    return paiement


def lister_paiements(db: Session, commande_id: int) -> list[Paiement]:
    commande = lire_commande(db, commande_id)
    return list(commande.paiements)


def annuler_paiement(db: Session, paiement_id: int) -> None:
    paiement = db.get(Paiement, paiement_id)
    if paiement is None:
        raise HTTPException(status_code=404, detail="Paiement introuvable")

    # RG17 : on retire le paiement puis on recalcule le payé et le solde
    commande = db.get(Commande, paiement.commande_id)
    commande.paiements.remove(paiement)
    recalculer_montants(commande)
    db.flush()
