from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import Commande, HistoriqueStatut, Utilisateur
from app.schemas.commande import ChangementStatut
from app.services.commandes import lire_commande

# Workflow : statut actuel -> statuts possibles ensuite
# (« livree » ne s'obtient que par la confirmation de la livraison, RG13)
TRANSITIONS = {
    "en_attente": ["en_coupe", "annulee"],
    "en_coupe": ["en_couture", "annulee"],
    "en_couture": ["essayage", "terminee", "annulee"],
    "essayage": ["retouches", "terminee", "annulee"],
    "retouches": ["essayage", "terminee", "annulee"],
    "terminee": ["livree"],
    "livree": [],
    "annulee": [],
}


def enregistrer_historique(
    db: Session,
    commande: Commande,
    ancien_statut: str | None,
    nouveau_statut: str,
    commentaire: str | None,
    utilisateur: Utilisateur,
) -> None:
    """RG15 : chaque changement de statut est historisé."""
    db.add(
        HistoriqueStatut(
            commande_id=commande.id,
            ancien_statut=ancien_statut,
            nouveau_statut=nouveau_statut,
            commentaire=commentaire,
            utilisateur_id=utilisateur.id,
        )
    )


def texte_statuts_possibles(statut: str) -> str:
    possibles = TRANSITIONS[statut]
    if statut == "terminee":
        return "livree (uniquement par la confirmation de livraison)"
    if len(possibles) == 0:
        return "aucun (statut final)"
    return ", ".join(sorted(possibles))


def changer_statut(
    db: Session, commande_id: int, donnees: ChangementStatut, utilisateur: Utilisateur
) -> Commande:
    commande = lire_commande(db, commande_id)
    ancien_statut = commande.statut
    nouveau_statut = donnees.statut
    commentaire = donnees.commentaire
    if commentaire is not None:
        commentaire = commentaire.strip()
        if commentaire == "":
            commentaire = None

    # RG14 : le tailleur ne peut pas annuler
    if nouveau_statut == "annulee" and utilisateur.role == "tailleur":
        raise HTTPException(status_code=403, detail="Un tailleur ne peut pas annuler une commande")

    # RG13 : demander le statut déjà en cours
    if nouveau_statut == ancien_statut:
        raise HTTPException(
            status_code=409,
            detail="La commande est déjà au statut « " + ancien_statut + " »",
        )

    # RG13 : « livree » résulte de la confirmation de livraison
    if nouveau_statut == "livree":
        raise HTTPException(
            status_code=409,
            detail="Le statut « livree » ne peut pas être posé ici : "
            "confirmez la livraison (POST /commandes/{id}/livraison/confirmer)",
        )

    if nouveau_statut not in TRANSITIONS[ancien_statut]:
        raise HTTPException(
            status_code=409,
            detail="Transition interdite : " + ancien_statut + " → " + nouveau_statut
            + ". Statuts possibles : " + texte_statuts_possibles(ancien_statut),
        )

    # RG14 : annuler une commande qui a reçu un acompte exige un commentaire
    if nouveau_statut == "annulee" and commande.montant_paye > 0 and commentaire is None:
        raise HTTPException(
            status_code=422,
            detail="Cette commande a reçu un acompte de " + str(commande.montant_paye)
            + " FCFA : précisez dans le commentaire ce que devient cet argent",
        )

    commande.statut = nouveau_statut
    enregistrer_historique(db, commande, ancien_statut, nouveau_statut, commentaire, utilisateur)
    db.flush()
    return commande


def lire_historique(db: Session, commande_id: int) -> list[HistoriqueStatut]:
    commande = lire_commande(db, commande_id)
    return list(commande.historique)
