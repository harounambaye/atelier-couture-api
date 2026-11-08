from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Utilisateur
from app.schemas.utilisateur import UtilisateurCreation, UtilisateurModification
from app.security import hacher_mot_de_passe


def creer_utilisateur(db: Session, donnees: UtilisateurCreation) -> Utilisateur:
    existant = db.scalars(select(Utilisateur).where(Utilisateur.email == donnees.email)).first()
    if existant is not None:
        raise HTTPException(status_code=409, detail="Un compte avec cet e-mail existe déjà")

    existant = db.scalars(
        select(Utilisateur).where(Utilisateur.telephone == donnees.telephone)
    ).first()
    if existant is not None:
        raise HTTPException(status_code=409, detail="Un compte avec ce téléphone existe déjà")

    utilisateur = Utilisateur(
        email=donnees.email,
        telephone=donnees.telephone,
        nom_complet=donnees.nom_complet,
        mot_de_passe_hash=hacher_mot_de_passe(donnees.mot_de_passe),
        role=donnees.role,
        actif=True,
    )
    db.add(utilisateur)
    db.flush()
    return utilisateur


def lister_utilisateurs(db: Session) -> list[Utilisateur]:
    requete = select(Utilisateur).order_by(Utilisateur.nom_complet, Utilisateur.id)
    return list(db.scalars(requete).all())


def lire_utilisateur(db: Session, utilisateur_id: int) -> Utilisateur:
    utilisateur = db.get(Utilisateur, utilisateur_id)
    if utilisateur is None:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    return utilisateur


def modifier_utilisateur(
    db: Session,
    utilisateur_id: int,
    donnees: UtilisateurModification,
    admin_connecte: Utilisateur,
) -> Utilisateur:
    utilisateur = lire_utilisateur(db, utilisateur_id)
    changements = donnees.model_dump(exclude_unset=True)

    # RG24 : un admin ne peut ni se désactiver ni retirer son propre rôle admin
    if utilisateur.id == admin_connecte.id:
        if changements.get("actif") is False:
            raise HTTPException(
                status_code=409, detail="Vous ne pouvez pas désactiver votre propre compte"
            )
        if "role" in changements and changements["role"] != "admin":
            raise HTTPException(
                status_code=409, detail="Vous ne pouvez pas retirer votre propre rôle administrateur"
            )

    if "nom_complet" in changements and changements["nom_complet"] is not None:
        utilisateur.nom_complet = changements["nom_complet"]
    if "role" in changements and changements["role"] is not None:
        utilisateur.role = changements["role"]
    if "actif" in changements and changements["actif"] is not None:
        utilisateur.actif = changements["actif"]
    if "mot_de_passe" in changements and changements["mot_de_passe"] is not None:
        utilisateur.mot_de_passe_hash = hacher_mot_de_passe(changements["mot_de_passe"])

    db.flush()
    return utilisateur
