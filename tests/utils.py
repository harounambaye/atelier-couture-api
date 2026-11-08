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
