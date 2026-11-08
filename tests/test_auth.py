from datetime import datetime, timedelta, timezone

import jwt

from app.config import settings
from tests.utils import creer_utilisateur, entete_auth, se_connecter

URL_ME = "/api/v1/auth/me"


# ---------- Connexion (route 1) ----------

def test_login_par_email(client, db):
    creer_utilisateur(db, "accueil", "accueil@atelier.sn", "771111111")
    reponse = se_connecter(client, "accueil@atelier.sn")
    assert reponse.status_code == 200
    donnees = reponse.json()
    assert donnees["token_type"] == "bearer"
    assert donnees["expires_in"] == settings.access_token_expire_minutes * 60
    assert donnees["access_token"] != ""


def test_login_email_insensible_a_la_casse(client, db):
    creer_utilisateur(db, "accueil", "accueil@atelier.sn", "771111111")
    reponse = se_connecter(client, "ACCUEIL@Atelier.sn")
    assert reponse.status_code == 200


def test_login_par_telephone_non_normalise(client, db):
    creer_utilisateur(db, "tailleur", "tailleur@atelier.sn", "772222222")
    assert se_connecter(client, "77 222 22 22").status_code == 200
    assert se_connecter(client, "77-222-22-22").status_code == 200


def test_rg23_meme_message_compte_inconnu_ou_mot_de_passe_faux(client, db):
    creer_utilisateur(db, "accueil", "accueil@atelier.sn", "771111111")
    mauvais_mdp = se_connecter(client, "accueil@atelier.sn", "mauvais_mdp")
    inconnu = se_connecter(client, "inconnu@atelier.sn")
    assert mauvais_mdp.status_code == 401
    assert inconnu.status_code == 401
    assert mauvais_mdp.json() == inconnu.json()


def test_login_compte_desactive_refuse(client, db):
    creer_utilisateur(db, "accueil", "accueil@atelier.sn", "771111111", actif=False)
    reponse = se_connecter(client, "accueil@atelier.sn")
    assert reponse.status_code == 401


# ---------- Profil (route 2) ----------

def test_me_renvoie_le_profil_sans_donnee_sensible(client, db):
    creer_utilisateur(db, "accueil", "accueil@atelier.sn", "771111111")
    reponse = client.get(URL_ME, headers=entete_auth(client, "accueil@atelier.sn"))
    assert reponse.status_code == 200
    donnees = reponse.json()
    assert donnees["email"] == "accueil@atelier.sn"
    assert donnees["role"] == "accueil"
    assert "mot_de_passe_hash" not in donnees
    assert "mot_de_passe" not in donnees


def test_me_sans_jeton_401(client):
    reponse = client.get(URL_ME)
    assert reponse.status_code == 401


def test_me_jeton_invalide_401(client):
    reponse = client.get(URL_ME, headers={"Authorization": "Bearer abc"})
    assert reponse.status_code == 401


def test_rg22_jeton_expire_401(client, db):
    utilisateur = creer_utilisateur(db, "accueil", "accueil@atelier.sn", "771111111")
    expiration = datetime.now(timezone.utc) - timedelta(minutes=1)
    jeton = jwt.encode(
        {"sub": str(utilisateur.id), "exp": expiration},
        settings.secret_key,
        algorithm=settings.algorithm,
    )
    reponse = client.get(URL_ME, headers={"Authorization": "Bearer " + jeton})
    assert reponse.status_code == 401


def test_rg22_jeton_signe_avec_autre_cle_401(client, db):
    utilisateur = creer_utilisateur(db, "accueil", "accueil@atelier.sn", "771111111")
    expiration = datetime.now(timezone.utc) + timedelta(minutes=10)
    jeton = jwt.encode(
        {"sub": str(utilisateur.id), "exp": expiration},
        "une_autre_cle_secrete_de_32_caracteres!",
        algorithm="HS256",
    )
    reponse = client.get(URL_ME, headers={"Authorization": "Bearer " + jeton})
    assert reponse.status_code == 401


def test_rg22_compte_desactive_avec_jeton_encore_valide_401(client, db):
    utilisateur = creer_utilisateur(db, "accueil", "accueil@atelier.sn", "771111111")
    entete = entete_auth(client, "accueil@atelier.sn")
    assert client.get(URL_ME, headers=entete).status_code == 200

    utilisateur.actif = False
    db.commit()

    reponse = client.get(URL_ME, headers=entete)
    assert reponse.status_code == 401


def test_rg21_mot_de_passe_stocke_hache(db):
    utilisateur = creer_utilisateur(db, "accueil", "accueil@atelier.sn", "771111111")
    assert utilisateur.mot_de_passe_hash.startswith("$argon2")
    assert "MotDePasse123" not in utilisateur.mot_de_passe_hash