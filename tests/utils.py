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