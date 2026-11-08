from sqlalchemy import select

from app.config import settings
from app.database import SessionLocal
from app.models import Utilisateur
from app.security import hacher_mot_de_passe
from app.services.telephone import normaliser_telephone, telephone_est_valide


def creer_admin(db) -> None:
    email = settings.admin_email.strip().lower()
    telephone = normaliser_telephone(settings.admin_telephone)

    if len(settings.admin_mot_de_passe) < 8:
        raise SystemExit("ADMIN_MOT_DE_PASSE doit contenir au moins 8 caractères")
    if not telephone_est_valide(telephone):
        raise SystemExit("ADMIN_TELEPHONE invalide (6 à 20 chiffres, + initial facultatif)")

    existant = db.scalars(select(Utilisateur).where(Utilisateur.email == email)).first()
    if existant is not None:
        print(f"Administrateur déjà présent : {email}")
        return

    admin = Utilisateur(
        email=email,
        telephone=telephone,
        nom_complet=settings.admin_nom_complet,
        mot_de_passe_hash=hacher_mot_de_passe(settings.admin_mot_de_passe),
        role="admin",
        actif=True,
    )
    db.add(admin)
    print(f"Administrateur créé : {email}")


def main() -> None:
    db = SessionLocal()
    try:
        creer_admin(db)
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    main()