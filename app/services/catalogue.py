from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import TypeVetement
from app.schemas.type_vetement import TypeVetementCreation, TypeVetementModification


def verifier_nom_libre(db: Session, nom: str, type_id_exclu: int | None = None) -> None:
    requete = select(TypeVetement).where(TypeVetement.nom == nom)
    if type_id_exclu is not None:
        requete = requete.where(TypeVetement.id != type_id_exclu)
    if db.scalars(requete).first() is not None:
        raise HTTPException(status_code=409, detail="Une prestation porte déjà ce nom")


def creer_type_vetement(db: Session, donnees: TypeVetementCreation) -> TypeVetement:
    verifier_nom_libre(db, donnees.nom)
    type_vetement = TypeVetement(
        nom=donnees.nom,
        description=donnees.description,
        prix_base=donnees.prix_base,
        delai_jours=donnees.delai_jours,
        actif=True,
    )
    db.add(type_vetement)
    db.flush()
    return type_vetement


def lister_types_vetement(db: Session, actifs_seulement: bool) -> list[TypeVetement]:
    requete = select(TypeVetement)
    if actifs_seulement:
        requete = requete.where(TypeVetement.actif.is_(True))
    requete = requete.order_by(TypeVetement.nom)
    return list(db.scalars(requete).all())


def lire_type_vetement(db: Session, type_id: int) -> TypeVetement:
    type_vetement = db.get(TypeVetement, type_id)
    if type_vetement is None:
        raise HTTPException(status_code=404, detail="Prestation introuvable")
    return type_vetement


def modifier_type_vetement(
    db: Session, type_id: int, donnees: TypeVetementModification
) -> TypeVetement:
    type_vetement = lire_type_vetement(db, type_id)
    changements = donnees.model_dump(exclude_unset=True)

    if "nom" in changements:
        verifier_nom_libre(db, changements["nom"], type_id_exclu=type_vetement.id)

    # Les anciennes commandes gardent leur prix : elles ont leur propre prix_unitaire
    for champ, valeur in changements.items():
        setattr(type_vetement, champ, valeur)

    db.flush()
    return type_vetement
