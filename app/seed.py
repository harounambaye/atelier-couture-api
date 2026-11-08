from sqlalchemy import select

from app.config import settings
from app.database import SessionLocal
from app.models import TypeVetement, Utilisateur
from app.security import hacher_mot_de_passe
from app.services.telephone import normaliser_telephone, telephone_est_valide

# Annexe B du cahier des charges : (nom, description, prix_base en FCFA, délai en jours)
CATALOGUE_DE_DEPART = [
    ("Boubou", "Boubou homme en bazin ou brodé", 35000, 10),
    ("Costume 2 pièces", "Veste et pantalon", 85000, 14),
    ("Robe", "Robe sur mesure", 30000, 7),
    ("Ensemble wax", "Tenue deux pièces en wax", 25000, 7),
    ("Chemise", "Chemise sur mesure", 15000, 5),
    ("Pantalon", "Pantalon sur mesure", 12000, 4),
    ("Retouche", "Ourlet, rétrécissement, remplacement de fermeture", 3000, 2),
]


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


def creer_catalogue(db) -> None:
    """Ajoute les prestations de l'annexe B qui n'existent pas encore (idempotent)."""
    for nom, description, prix_base, delai_jours in CATALOGUE_DE_DEPART:
        existant = db.scalars(select(TypeVetement).where(TypeVetement.nom == nom)).first()
        if existant is not None:
            continue
        db.add(
            TypeVetement(
                nom=nom,
                description=description,
                prix_base=prix_base,
                delai_jours=delai_jours,
                actif=True,
            )
        )
        print(f"Prestation créée : {nom}")


def main() -> None:
    db = SessionLocal()
    try:
        creer_admin(db)
        creer_catalogue(db)
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    main()
