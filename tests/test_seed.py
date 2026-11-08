from sqlalchemy import func, select

from app.models import Utilisateur
from app.seed import creer_admin


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