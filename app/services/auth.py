from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Utilisateur
from app.security import verifier_mot_de_passe
from app.services.telephone import normaliser_telephone


def authentifier(db: Session, identifiant: str, mot_de_passe: str) -> Utilisateur:
    identifiant = identifiant.strip()

    # Un "@" => e-mail ; sinon => numéro de téléphone
    if "@" in identifiant:
        requete = select(Utilisateur).where(Utilisateur.email == identifiant.lower())
    else:
        telephone = normaliser_telephone(identifiant)
        requete = select(Utilisateur).where(Utilisateur.telephone == telephone)

    utilisateur = db.scalars(requete).first()

    # RG23 : même message si le compte n'existe pas ou si le mot de passe est faux
    if utilisateur is None or not verifier_mot_de_passe(mot_de_passe, utilisateur.mot_de_passe_hash):
        raise HTTPException(
            status_code=401,
            detail="Identifiants incorrects",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not utilisateur.actif:
        raise HTTPException(
            status_code=401,
            detail="Compte désactivé",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return utilisateur