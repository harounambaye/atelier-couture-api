from datetime import date

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Client, Commande, Livraison, Utilisateur
from app.schemas.livraison import (
    ConfirmationLivraison,
    LivraisonPlanification,
    LivraisonTournee,
)
from app.services.commandes import (
    calculer_solde,
    lire_commande,
    verifier_date_prevue,
    verifier_modifiable,
)
from app.services.statuts import enregistrer_historique


def planifier_livraison(
    db: Session, commande_id: int, donnees: LivraisonPlanification
) -> Livraison:
    commande = lire_commande(db, commande_id)
    verifier_modifiable(commande)  # 409 si la commande est livrée ou annulée

    # RG18 : une livraison à domicile exige une adresse
    adresse = donnees.adresse
    if adresse is not None:
        adresse = adresse.strip()
        if adresse == "":
            adresse = None
    if donnees.mode == "domicile" and adresse is None:
        raise HTTPException(
            status_code=422, detail="Une livraison à domicile exige une adresse de livraison"
        )

    verifier_date_prevue(donnees.date_prevue, commande.date_commande)

    # RG18 : replanifier modifie la livraison existante (il n'y en a jamais deux)
    livraison = commande.livraison
    if livraison is None:
        livraison = Livraison(statut="planifiee")
        commande.livraison = livraison

    livraison.mode = donnees.mode
    livraison.adresse = adresse
    livraison.livreur = donnees.livreur
    livraison.date_prevue = donnees.date_prevue
    livraison.notes = donnees.notes

    # RG18 : planifier met à jour la date de livraison prévue de la commande
    commande.date_livraison_prevue = donnees.date_prevue

    db.flush()
    return livraison


def lire_livraison(db: Session, commande_id: int) -> Livraison:
    commande = lire_commande(db, commande_id)
    if commande.livraison is None:
        raise HTTPException(status_code=404, detail="Aucune livraison pour cette commande")
    return commande.livraison


def confirmer_livraison(
    db: Session,
    commande_id: int,
    donnees: ConfirmationLivraison | None,
    utilisateur: Utilisateur,
) -> Commande:
    if donnees is None:
        donnees = ConfirmationLivraison()

    commande = lire_commande(db, commande_id)

    # RG19 : la commande doit être terminée
    if commande.statut != "terminee":
        raise HTTPException(
            status_code=409,
            detail="Seule une commande « terminee » peut être livrée (statut actuel : « "
            + commande.statut + " »)",
        )

    # RG19 : la commande doit être soldée, sauf autorisation explicite
    solde = calculer_solde(commande)
    if solde > 0 and not donnees.autoriser_solde_impaye:
        raise HTTPException(
            status_code=409,
            detail="La commande n'est pas soldée : il reste " + str(solde)
            + " FCFA à payer. Encaissez le solde ou utilisez autoriser_solde_impaye=true",
        )

    date_effective = donnees.date_effective
    if date_effective is None:
        date_effective = date.today()
    if date_effective > date.today():
        raise HTTPException(
            status_code=422, detail="La date de livraison effective ne peut pas être dans le futur"
        )

    # RG20 : sans planification préalable, on crée un retrait à l'atelier
    livraison = commande.livraison
    if livraison is None:
        livraison = Livraison(
            mode="retrait_atelier",
            date_prevue=commande.date_livraison_prevue,
            statut="planifiee",
        )
        commande.livraison = livraison

    livraison.date_effective = date_effective
    livraison.statut = "livree"

    commande.statut = "livree"
    commande.date_livraison_reelle = date_effective

    commentaire = "Livraison confirmée"
    if solde > 0:
        commentaire = "Livraison confirmée avec un solde impayé de " + str(solde) + " FCFA"
    enregistrer_historique(db, commande, "terminee", "livree", commentaire, utilisateur)

    db.flush()
    return commande


def lister_livraisons(
    db: Session, statut: str | None, date_min: date | None, date_max: date | None
) -> list[LivraisonTournee]:
    requete = (
        select(Livraison, Commande, Client)
        .join(Commande, Commande.id == Livraison.commande_id)
        .join(Client, Client.id == Commande.client_id)
    )
    if statut is not None:
        requete = requete.where(Livraison.statut == statut)
    if date_min is not None:
        requete = requete.where(Livraison.date_prevue >= date_min)
    if date_max is not None:
        requete = requete.where(Livraison.date_prevue <= date_max)
    requete = requete.order_by(Livraison.date_prevue, Livraison.id)

    tournee = []
    for livraison, commande, client in db.execute(requete).all():
        tournee.append(
            LivraisonTournee(
                id=livraison.id,
                commande_id=commande.id,
                numero_commande=commande.numero,
                client_nom=client.prenom + " " + client.nom,
                client_telephone=client.telephone,
                solde_commande=calculer_solde(commande),
                mode=livraison.mode,
                adresse=livraison.adresse,
                livreur=livraison.livreur,
                date_prevue=livraison.date_prevue,
                date_effective=livraison.date_effective,
                statut=livraison.statut,
                notes=livraison.notes,
            )
        )
    return tournee
