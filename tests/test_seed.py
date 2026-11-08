from sqlalchemy import func, select

from app.models import TypeVetement, Utilisateur
from app.seed import CATALOGUE_DE_DEPART, creer_admin, creer_catalogue


def test_seed_cree_l_admin_une_seule_fois(db):
    creer_admin(db)
    db.commit()
    creer_admin(db)
    db.commit()

    nombre = db.scalar(select(func.count()).select_from(Utilisateur))
    assert nombre == 1

    admin = db.scalars(select(Utilisateur)).first()
    assert admin.role == "admin"
    assert admin.actif is True


def test_seed_cree_le_catalogue_une_seule_fois(db):
    creer_catalogue(db)
    db.commit()
    creer_catalogue(db)
    db.commit()

    nombre = db.scalar(select(func.count()).select_from(TypeVetement))
    assert nombre == len(CATALOGUE_DE_DEPART) == 7

    boubou = db.scalars(select(TypeVetement).where(TypeVetement.nom == "Boubou")).first()
    assert boubou.prix_base == 35000
    assert boubou.delai_jours == 10


def test_seed_ne_modifie_pas_une_prestation_existante(db):
    creer_catalogue(db)
    db.commit()
    boubou = db.scalars(select(TypeVetement).where(TypeVetement.nom == "Boubou")).first()
    boubou.prix_base = 40000
    db.commit()

    creer_catalogue(db)
    db.commit()
    db.refresh(boubou)
    assert boubou.prix_base == 40000
