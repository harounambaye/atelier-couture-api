from datetime import date, timedelta

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.models import Client, Commande, LigneCommande, Livraison, Paiement, TypeVetement
from app.models.commande import STATUTS
from app.schemas.statistiques import (
    ChiffreAffaires,
    PeriodeChiffreAffaires,
    StatistiqueClient,
    StatistiqueTypeVetement,
    TableauDeBord,
)
from app.services.commandes import condition_en_retard

# Une commande annulée ne compte jamais dans le chiffre d'affaires ni dans les soldes
NON_ANNULEE = Commande.statut != "annulee"


def somme_ou_zero(valeur) -> int:
    if valeur is None:
        return 0
    return int(valeur)


def periode_par_defaut(date_debut: date | None, date_fin: date | None) -> tuple[date, date]:
    """Par défaut : du 1er du mois courant jusqu'à aujourd'hui. 422 si début > fin."""
    aujourdhui = date.today()
    if date_debut is None:
        date_debut = aujourdhui.replace(day=1)
    if date_fin is None:
        date_fin = aujourdhui
    if date_debut > date_fin:
        raise HTTPException(
            status_code=422, detail="date_debut doit être antérieure ou égale à date_fin"
        )
    return date_debut, date_fin


def tableau_de_bord(db: Session) -> TableauDeBord:
    aujourdhui = date.today()
    debut_mois = aujourdhui.replace(day=1)
    # Premier jour du mois suivant (le 28 + 4 jours tombe toujours le mois suivant)
    debut_mois_suivant = (debut_mois.replace(day=28) + timedelta(days=4)).replace(day=1)

    # Chiffre d'affaires du mois : commandes non annulées, datées à la date de commande
    chiffre_affaires_mois = somme_ou_zero(
        db.scalar(
            select(func.sum(Commande.montant_total)).where(
                NON_ANNULEE,
                Commande.date_commande >= debut_mois,
                Commande.date_commande < debut_mois_suivant,
            )
        )
    )
    nb_commandes_mois = db.scalar(
        select(func.count(Commande.id)).where(
            NON_ANNULEE,
            Commande.date_commande >= debut_mois,
            Commande.date_commande < debut_mois_suivant,
        )
    )

    # Encaissé du mois : paiements datés à la date de paiement
    encaisse_mois = somme_ou_zero(
        db.scalar(
            select(func.sum(Paiement.montant)).where(
                Paiement.date_paiement >= debut_mois,
                Paiement.date_paiement < debut_mois_suivant,
            )
        )
    )

    # Reste à encaisser : somme des soldes des commandes non annulées
    reste_a_encaisser = somme_ou_zero(
        db.scalar(
            select(func.sum(Commande.montant_total - Commande.montant_paye)).where(NON_ANNULEE)
        )
    )

    # Nombre de commandes par statut : tous les statuts sont présents, même à 0
    commandes_par_statut = {}
    for statut in STATUTS:
        commandes_par_statut[statut] = 0
    lignes = db.execute(select(Commande.statut, func.count(Commande.id)).group_by(Commande.statut))
    for statut, nombre in lignes.all():
        commandes_par_statut[statut] = nombre

    nb_en_retard = db.scalar(select(func.count(Commande.id)).where(condition_en_retard()))

    livraisons_du_jour = db.scalar(
        select(func.count(Livraison.id)).where(
            Livraison.statut == "planifiee", Livraison.date_prevue == aujourdhui
        )
    )

    return TableauDeBord(
        chiffre_affaires_mois=chiffre_affaires_mois,
        encaisse_mois=encaisse_mois,
        nb_commandes_mois=nb_commandes_mois,
        reste_a_encaisser=reste_a_encaisser,
        commandes_par_statut=commandes_par_statut,
        nb_commandes_en_retard=nb_en_retard,
        commandes_pretes_a_livrer=commandes_par_statut["terminee"],
        livraisons_du_jour=livraisons_du_jour,
    )


def chiffre_affaires(
    db: Session, granularite: str, date_debut: date | None, date_fin: date | None
) -> ChiffreAffaires:
    date_debut, date_fin = periode_par_defaut(date_debut, date_fin)

    if granularite == "jour":
        modele = "YYYY-MM-DD"
    else:
        modele = "YYYY-MM"

    # CA : commandes non annulées, à la date de commande
    cle_commande = func.to_char(Commande.date_commande, modele)
    requete_ca = (
        select(cle_commande, func.sum(Commande.montant_total), func.count(Commande.id))
        .where(NON_ANNULEE, Commande.date_commande >= date_debut, Commande.date_commande <= date_fin)
        .group_by(cle_commande)
    )

    # Encaissements : paiements, à la date de paiement
    cle_paiement = func.to_char(Paiement.date_paiement, modele)
    requete_encaisse = (
        select(cle_paiement, func.sum(Paiement.montant))
        .where(Paiement.date_paiement >= date_debut, Paiement.date_paiement <= date_fin)
        .group_by(cle_paiement)
    )

    # On fusionne : seules les périodes avec de l'activité apparaissent
    par_periode = {}
    for periode, total, nombre in db.execute(requete_ca).all():
        par_periode[periode] = {"chiffre_affaires": int(total), "encaissements": 0, "nb": nombre}
    for periode, total in db.execute(requete_encaisse).all():
        if periode not in par_periode:
            par_periode[periode] = {"chiffre_affaires": 0, "encaissements": 0, "nb": 0}
        par_periode[periode]["encaissements"] = int(total)

    periodes = []
    for periode in sorted(par_periode.keys()):
        valeurs = par_periode[periode]
        periodes.append(
            PeriodeChiffreAffaires(
                periode=periode,
                chiffre_affaires=valeurs["chiffre_affaires"],
                encaissements=valeurs["encaissements"],
                nb_commandes=valeurs["nb"],
            )
        )

    return ChiffreAffaires(
        granularite=granularite, date_debut=date_debut, date_fin=date_fin, periodes=periodes
    )


def types_vetement(
    db: Session, date_debut: date | None, date_fin: date | None
) -> list[StatistiqueTypeVetement]:
    date_debut, date_fin = periode_par_defaut(date_debut, date_fin)

    ca = func.sum(LigneCommande.quantite * LigneCommande.prix_unitaire)
    requete = (
        select(
            TypeVetement.id,
            TypeVetement.nom,
            func.sum(LigneCommande.quantite),
            ca,
        )
        .join(LigneCommande, LigneCommande.type_vetement_id == TypeVetement.id)
        .join(Commande, Commande.id == LigneCommande.commande_id)
        .where(NON_ANNULEE, Commande.date_commande >= date_debut, Commande.date_commande <= date_fin)
        .group_by(TypeVetement.id, TypeVetement.nom)
        .order_by(ca.desc(), TypeVetement.nom)
    )

    resultat = []
    for type_id, nom, quantite, total in db.execute(requete).all():
        resultat.append(
            StatistiqueTypeVetement(
                type_vetement_id=type_id,
                nom=nom,
                quantite_vendue=int(quantite),
                chiffre_affaires_avant_remise=int(total),
            )
        )
    return resultat


def top_clients(db: Session, limite: int) -> list[StatistiqueClient]:
    chiffre = func.sum(Commande.montant_total)
    paye = func.sum(Commande.montant_paye)
    requete = (
        select(Client.id, Client.prenom, Client.nom, func.count(Commande.id), chiffre, paye)
        .join(Commande, Commande.client_id == Client.id)
        .where(NON_ANNULEE)
        .group_by(Client.id, Client.prenom, Client.nom)
        .order_by(chiffre.desc(), Client.nom, Client.id)
        .limit(limite)
    )

    resultat = []
    for client_id, prenom, nom, nombre, total, total_paye in db.execute(requete).all():
        resultat.append(
            StatistiqueClient(
                client_id=client_id,
                client_nom=prenom + " " + nom,
                nb_commandes=nombre,
                chiffre_affaires=int(total),
                solde_du=int(total) - int(total_paye),
            )
        )
    return resultat


def lister_impayes(db: Session, limit: int, offset: int) -> tuple[list[Commande], int]:
    """Commandes non annulées non soldées, les plus urgentes d'abord."""
    requete = select(Commande).where(NON_ANNULEE, Commande.montant_total > Commande.montant_paye)

    total = db.scalar(select(func.count()).select_from(requete.subquery()))

    requete = (
        requete.options(joinedload(Commande.client))
        .order_by(Commande.date_livraison_prevue, Commande.id)
        .limit(limit)
        .offset(offset)
    )
    commandes = list(db.scalars(requete).unique().all())
    return commandes, total
