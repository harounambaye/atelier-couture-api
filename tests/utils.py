from app.models import Utilisateur
from app.security import hacher_mot_de_passe

MOT_DE_PASSE = "MotDePasse123"


def creer_utilisateur(db, role, email, telephone, actif=True):
    utilisateur = Utilisateur(
        email=email,
        telephone=telephone,
        nom_complet="Utilisateur " + role,
        mot_de_passe_hash=hacher_mot_de_passe(MOT_DE_PASSE),
        role=role,
        actif=actif,
    )
    db.add(utilisateur)
    db.commit()
    db.refresh(utilisateur)
    return utilisateur


def se_connecter(client, identifiant, mot_de_passe=MOT_DE_PASSE):
    return client.post(
        "/api/v1/auth/login",
        data={"username": identifiant, "password": mot_de_passe},
    )


def entete_auth(client, identifiant, mot_de_passe=MOT_DE_PASSE):
    reponse = se_connecter(client, identifiant, mot_de_passe)
    jeton = reponse.json()["access_token"]
    return {"Authorization": "Bearer " + jeton}

TELEPHONES_ROLES = {"admin": "700000001", "accueil": "700000002", "tailleur": "700000003"}


def entete_pour_role(db, client, role):
    """Crée un compte de ce rôle et renvoie l'en-tête Authorization."""
    email = role + "@test.sn"
    creer_utilisateur(db, role, email, TELEPHONES_ROLES[role])
    return entete_auth(client, email)


def creer_client_bd(db, telephone="771234567", nom="Diop", prenom="Fatou", genre="femme"):
    from app.models import Client

    nouveau = Client(nom=nom, prenom=prenom, telephone=telephone, genre=genre)
    db.add(nouveau)
    db.commit()
    db.refresh(nouveau)
    return nouveau


def creer_prestation_bd(db, nom="Boubou", prix_base=35000, delai_jours=10, actif=True):
    from app.models import TypeVetement

    prestation = TypeVetement(
        nom=nom, prix_base=prix_base, delai_jours=delai_jours, actif=actif
    )
    db.add(prestation)
    db.commit()
    db.refresh(prestation)
    return prestation


def creer_mesure_bd(db, client_bd, tailleur_id, date_prise=None, tour_cou=38):
    from datetime import date

    from app.models import Mesure

    mesure = Mesure(
        client_id=client_bd.id,
        date_prise=date_prise or date.today(),
        prise_par_id=tailleur_id,
        tour_cou=tour_cou,
    )
    db.add(mesure)
    db.commit()
    db.refresh(mesure)
    return mesure


def creer_commande_api(client, entete, client_id, lignes, **extras):
    """lignes = liste de dictionnaires {type_vetement_id, quantite, prix_unitaire?}"""
    donnees = {"client_id": client_id, "lignes": lignes}
    donnees.update(extras)
    return client.post("/api/v1/commandes", json=donnees, headers=entete)
