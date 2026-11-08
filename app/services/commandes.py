from datetime import date, timedelta
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import and_, func, not_, select
from sqlalchemy.orm import Session, joinedload

from app.models import (
    Client,
    Commande,
    HistoriqueStatut,
    LigneCommande,
    Mesure,
    TypeVetement,
    Utilisateur,
)
from app.schemas.commande import (
    CommandeCreation,
    CommandeDetail,
    CommandeModification,
    CommandeResume,
    LigneCommandeCreation,
    LigneCommandeLecture,
    ResumeClient,
)
from app.services.clients import lire_client
from app.services.mesures import trouver_dernieres_mesures

STATUTS_FINAUX = ["livree", "annulee"]


# ---------- Calculs ----------


def somme_prestations(commande: Commande) -> int:
    somme = 0
    for ligne in commande.lignes:
        somme = somme + ligne.quantite * ligne.prix_unitaire
    return somme


def calculer_solde(commande: Commande) -> int:
    return commande.montant_total - commande.montant_paye


def est_en_retard(commande: Commande) -> bool:
    """RG11 : date prévue dépassée et commande ni livrée ni annulée."""
    if commande.statut in STATUTS_FINAUX:
        return False
    return commande.date_livraison_prevue < date.today()


def recalculer_montants(commande: Commande) -> None:
    """RG7 : total = somme des lignes - remise ; payé = somme des paiements."""
    commande.montant_total = somme_prestations(commande) - commande.remise
    paye = 0
    for paiement in commande.paiements:
        paye = paye + paiement.montant
    commande.montant_paye = paye


def nom_complet_client(client: Client) -> str:
    return client.prenom + " " + client.nom


# ---------- Conversion vers les schémas de lecture ----------


def construire_resume(commande: Commande) -> CommandeResume:
    return CommandeResume(
        id=commande.id,
        numero=commande.numero,
        client_id=commande.client_id,
        client_nom=nom_complet_client(commande.client),
        statut=commande.statut,
        date_commande=commande.date_commande,
        date_livraison_prevue=commande.date_livraison_prevue,
        date_livraison_reelle=commande.date_livraison_reelle,
        remise=commande.remise,
        montant_total=commande.montant_total,
        montant_paye=commande.montant_paye,
        solde=calculer_solde(commande),
        en_retard=est_en_retard(commande),
    )


def construire_detail(commande: Commande) -> CommandeDetail:
    lignes = []
    for ligne in commande.lignes:
        lignes.append(
            LigneCommandeLecture(
                id=ligne.id,
                type_vetement_id=ligne.type_vetement_id,
                type_vetement_nom=ligne.type_vetement.nom,
                description=ligne.description,
                quantite=ligne.quantite,
                prix_unitaire=ligne.prix_unitaire,
                sous_total=ligne.quantite * ligne.prix_unitaire,
            )
        )
    resume = construire_resume(commande)
    return CommandeDetail(
        **resume.model_dump(),
        mesure_id=commande.mesure_id,
        notes=commande.notes,
        cree_par_id=commande.cree_par_id,
        created_at=commande.created_at,
        updated_at=commande.updated_at,
        lignes=lignes,
        paiements=list(commande.paiements),
        livraison=commande.livraison,
    )


# ---------- Vérifications réutilisables ----------


def lire_commande(db: Session, commande_id: int) -> Commande:
    commande = db.get(Commande, commande_id)
    if commande is None:
        raise HTTPException(status_code=404, detail="Commande introuvable")
    return commande


def verifier_modifiable(commande: Commande) -> None:
    """RG12 : une commande livrée ou annulée n'est plus modifiable."""
    if commande.statut in STATUTS_FINAUX:
        raise HTTPException(
            status_code=409,
            detail="Une commande livrée ou annulée ne peut plus être modifiée",
        )


def lire_type_commandable(db: Session, type_vetement_id: int) -> TypeVetement:
    type_vetement = db.get(TypeVetement, type_vetement_id)
    if type_vetement is None:
        raise HTTPException(
            status_code=404, detail="Prestation " + str(type_vetement_id) + " introuvable"
        )
    # RG6 : une prestation inactive n'est pas commandable
    if not type_vetement.actif:
        raise HTTPException(
            status_code=422,
            detail="La prestation « " + type_vetement.nom + " » n'est plus commandable",
        )
    return type_vetement


def verifier_mesure_du_client(db: Session, mesure_id: int, client_id: int) -> None:
    """RG9 : la mesure rattachée doit appartenir au client de la commande."""
    mesure = db.get(Mesure, mesure_id)
    if mesure is None or mesure.client_id != client_id:
        raise HTTPException(
            status_code=422,
            detail="Ces mesures n'existent pas ou n'appartiennent pas au client de la commande",
        )


def verifier_remise(remise: int, somme: int) -> None:
    """RG7 : la remise ne peut pas dépasser la somme des prestations."""
    if remise > somme:
        raise HTTPException(
            status_code=422,
            detail="La remise (" + str(remise) + " FCFA) dépasse la somme des prestations ("
            + str(somme) + " FCFA)",
        )


def verifier_total_au_moins_paye(nouveau_total: int, commande: Commande) -> None:
    """RG7 : le total ne peut pas passer sous le montant déjà payé."""
    if nouveau_total < commande.montant_paye:
        raise HTTPException(
            status_code=409,
            detail="Le nouveau total (" + str(nouveau_total) + " FCFA) serait inférieur au montant "
            "déjà payé (" + str(commande.montant_paye) + " FCFA)",
        )


def verifier_date_prevue(date_prevue: date, date_commande: date) -> None:
    """RG8 : la date prévue ne peut pas précéder la date de commande."""
    if date_prevue < date_commande:
        raise HTTPException(
            status_code=422,
            detail="La date de livraison prévue ne peut pas précéder la date de commande",
        )


# ---------- Création ----------


def creer_commande(db: Session, donnees: CommandeCreation, utilisateur: Utilisateur) -> Commande:
    client = lire_client(db, donnees.client_id)

    # RG9 : mesures choisies, sinon dernières mesures du client s'il en a
    if donnees.mesure_id is not None:
        verifier_mesure_du_client(db, donnees.mesure_id, client.id)
        mesure_id = donnees.mesure_id
    else:
        dernieres = trouver_dernieres_mesures(db, client.id)
        mesure_id = None
        if dernieres is not None:
            mesure_id = dernieres.id

    # Lignes : prix par défaut = prix_base (RG6)
    lignes = []
    delai_maximum = 0
    for ligne_demandee in donnees.lignes:
        type_vetement = lire_type_commandable(db, ligne_demandee.type_vetement_id)
        prix_unitaire = ligne_demandee.prix_unitaire
        if prix_unitaire is None:
            prix_unitaire = type_vetement.prix_base
        lignes.append(
            LigneCommande(
                type_vetement_id=type_vetement.id,
                description=ligne_demandee.description,
                quantite=ligne_demandee.quantite,
                prix_unitaire=prix_unitaire,
            )
        )
        if type_vetement.delai_jours > delai_maximum:
            delai_maximum = type_vetement.delai_jours

    date_commande = date.today()

    # RG8 : date prévue par défaut = date de commande + plus long délai
    if donnees.date_livraison_prevue is not None:
        verifier_date_prevue(donnees.date_livraison_prevue, date_commande)
        date_prevue = donnees.date_livraison_prevue
    else:
        date_prevue = date_commande + timedelta(days=delai_maximum)

    commande = Commande(
        numero="TMP-" + uuid4().hex[:20],  # remplacé juste après (il dépend de l'id)
        client_id=client.id,
        mesure_id=mesure_id,
        statut="en_attente",
        date_commande=date_commande,
        date_livraison_prevue=date_prevue,
        remise=donnees.remise,
        notes=donnees.notes,
        cree_par_id=utilisateur.id,
    )
    commande.lignes = lignes

    # RG7 : montants calculés par le serveur
    verifier_remise(donnees.remise, somme_prestations(commande))
    recalculer_montants(commande)

    db.add(commande)
    db.flush()

    # RG5 : numéro CMD-AAAA-NNNNN
    commande.numero = "CMD-" + str(date_commande.year) + "-" + str(commande.id).zfill(5)

    # RG15 : première ligne d'historique (ancien statut vide)
    db.add(
        HistoriqueStatut(
            commande_id=commande.id,
            ancien_statut=None,
            nouveau_statut="en_attente",
            commentaire="Création de la commande",
            utilisateur_id=utilisateur.id,
        )
    )
    db.flush()
    return commande


# ---------- Lecture ----------


def condition_en_retard():
    return and_(
        Commande.date_livraison_prevue < date.today(),
        Commande.statut.notin_(STATUTS_FINAUX),
    )


def lister_commandes(
    db: Session,
    statut: str | None,
    client_id: int | None,
    en_retard: bool | None,
    date_min: date | None,
    date_max: date | None,
    numero: str | None,
    limit: int,
    offset: int,
) -> tuple[list[Commande], int]:
    requete = select(Commande)

    if statut is not None:
        requete = requete.where(Commande.statut == statut)
    if client_id is not None:
        requete = requete.where(Commande.client_id == client_id)
    if en_retard is True:
        requete = requete.where(condition_en_retard())
    if en_retard is False:
        requete = requete.where(not_(condition_en_retard()))
    if date_min is not None:
        requete = requete.where(Commande.date_commande >= date_min)
    if date_max is not None:
        requete = requete.where(Commande.date_commande <= date_max)
    if numero is not None:
        requete = requete.where(Commande.numero.ilike("%" + numero.strip() + "%"))

    total = db.scalar(select(func.count()).select_from(requete.subquery()))

    requete = (
        requete.options(joinedload(Commande.client))
        .order_by(Commande.date_commande.desc(), Commande.id.desc())
        .limit(limit)
        .offset(offset)
    )
    commandes = list(db.scalars(requete).unique().all())
    return commandes, total


def lister_commandes_du_client(
    db: Session, client_id: int, limit: int, offset: int
) -> tuple[list[Commande], int]:
    lire_client(db, client_id)  # 404 si le client n'existe pas
    return lister_commandes(db, None, client_id, None, None, None, None, limit, offset)


def resume_du_client(db: Session, client_id: int) -> ResumeClient:
    """Statistiques d'un client (les commandes annulées sont exclues)."""
    lire_client(db, client_id)
    requete = select(Commande).where(
        Commande.client_id == client_id, Commande.statut != "annulee"
    )
    commandes = list(db.scalars(requete).all())

    chiffre_affaires = 0
    total_paye = 0
    derniere = None
    for commande in commandes:
        chiffre_affaires = chiffre_affaires + commande.montant_total
        total_paye = total_paye + commande.montant_paye
        if derniere is None or commande.date_commande > derniere:
            derniere = commande.date_commande

    nombre_mesures = db.scalar(
        select(func.count()).select_from(Mesure).where(Mesure.client_id == client_id)
    )
    return ResumeClient(
        nb_commandes=len(commandes),
        chiffre_affaires=chiffre_affaires,
        total_paye=total_paye,
        solde_du=chiffre_affaires - total_paye,
        derniere_commande=derniere,
        a_des_mesures=nombre_mesures > 0,
    )


# ---------- Modification ----------


def modifier_commande(db: Session, commande_id: int, donnees: CommandeModification) -> Commande:
    commande = lire_commande(db, commande_id)
    verifier_modifiable(commande)  # RG12
    changements = donnees.model_dump(exclude_unset=True)

    if changements.get("mesure_id") is not None:
        verifier_mesure_du_client(db, changements["mesure_id"], commande.client_id)

    if "date_livraison_prevue" in changements:
        verifier_date_prevue(changements["date_livraison_prevue"], commande.date_commande)

    if "remise" in changements:
        somme = somme_prestations(commande)
        verifier_remise(changements["remise"], somme)
        verifier_total_au_moins_paye(somme - changements["remise"], commande)

    for champ, valeur in changements.items():
        setattr(commande, champ, valeur)

    recalculer_montants(commande)
    db.flush()
    return commande


def ajouter_ligne(
    db: Session, commande_id: int, donnees: LigneCommandeCreation
) -> Commande:
    commande = lire_commande(db, commande_id)
    verifier_modifiable(commande)  # RG12
    # RG10 : les lignes ne se modifient que si la commande est « en_attente »
    if commande.statut != "en_attente":
        raise HTTPException(
            status_code=409,
            detail="Les lignes ne sont modifiables que pour une commande « en_attente »",
        )

    type_vetement = lire_type_commandable(db, donnees.type_vetement_id)
    prix_unitaire = donnees.prix_unitaire
    if prix_unitaire is None:
        prix_unitaire = type_vetement.prix_base

    commande.lignes.append(
        LigneCommande(
            type_vetement_id=type_vetement.id,
            description=donnees.description,
            quantite=donnees.quantite,
            prix_unitaire=prix_unitaire,
        )
    )
    recalculer_montants(commande)
    db.flush()
    return commande


def retirer_ligne(db: Session, commande_id: int, ligne_id: int) -> Commande:
    commande = lire_commande(db, commande_id)
    verifier_modifiable(commande)  # RG12
    if commande.statut != "en_attente":
        raise HTTPException(
            status_code=409,
            detail="Les lignes ne sont modifiables que pour une commande « en_attente »",
        )

    ligne_a_retirer = None
    for ligne in commande.lignes:
        if ligne.id == ligne_id:
            ligne_a_retirer = ligne
    if ligne_a_retirer is None:
        raise HTTPException(status_code=404, detail="Ligne introuvable dans cette commande")

    # RG10 : une commande garde toujours au moins une ligne
    if len(commande.lignes) == 1:
        raise HTTPException(
            status_code=409, detail="Une commande doit garder au moins une ligne"
        )

    nouvelle_somme = somme_prestations(commande) - (
        ligne_a_retirer.quantite * ligne_a_retirer.prix_unitaire
    )
    verifier_remise(commande.remise, nouvelle_somme)
    verifier_total_au_moins_paye(nouvelle_somme - commande.remise, commande)

    commande.lignes.remove(ligne_a_retirer)
    recalculer_montants(commande)
    db.flush()
    return commande
