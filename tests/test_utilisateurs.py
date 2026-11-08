from tests.utils import MOT_DE_PASSE, creer_utilisateur, entete_auth

URL = "/api/v1/utilisateurs"

NOUVEAU = {
    "email": "Nouveau@Atelier.sn",
    "telephone": "77 000 11 22",
    "nom_complet": "Nouveau Compte",
    "mot_de_passe": "unmotdepasse",
    "role": "accueil",
}


def preparer_admin(db, client):
    admin = creer_utilisateur(db, "admin", "admin@test.sn", "700000001")
    return admin, entete_auth(client, "admin@test.sn")


def test_creation_201_sans_hash_et_normalisee(db, client):
    admin, entete = preparer_admin(db, client)
    reponse = client.post(URL, json=NOUVEAU, headers=entete)
    assert reponse.status_code == 201
    corps = reponse.json()
    assert corps["email"] == "nouveau@atelier.sn"
    assert corps["telephone"] == "770001122"
    assert "mot_de_passe_hash" not in corps
    assert "mot_de_passe" not in corps


def test_le_nouveau_compte_peut_se_connecter(db, client):
    admin, entete = preparer_admin(db, client)
    client.post(URL, json=NOUVEAU, headers=entete)
    reponse = client.post(
        "/api/v1/auth/login",
        data={"username": "nouveau@atelier.sn", "password": "unmotdepasse"},
    )
    assert reponse.status_code == 200


def test_doublon_email_409(db, client):
    admin, entete = preparer_admin(db, client)
    client.post(URL, json=NOUVEAU, headers=entete)
    autre = dict(NOUVEAU)
    autre["telephone"] = "780000000"
    assert client.post(URL, json=autre, headers=entete).status_code == 409


def test_doublon_telephone_409(db, client):
    admin, entete = preparer_admin(db, client)
    client.post(URL, json=NOUVEAU, headers=entete)
    autre = dict(NOUVEAU)
    autre["email"] = "autre@atelier.sn"
    assert client.post(URL, json=autre, headers=entete).status_code == 409


def test_mot_de_passe_trop_court_422(db, client):
    admin, entete = preparer_admin(db, client)
    donnees = dict(NOUVEAU)
    donnees["mot_de_passe"] = "court"
    assert client.post(URL, json=donnees, headers=entete).status_code == 422


def test_telephone_invalide_422(db, client):
    admin, entete = preparer_admin(db, client)
    donnees = dict(NOUVEAU)
    donnees["telephone"] = "abc"
    assert client.post(URL, json=donnees, headers=entete).status_code == 422


def test_role_invalide_422(db, client):
    admin, entete = preparer_admin(db, client)
    donnees = dict(NOUVEAU)
    donnees["role"] = "patron"
    assert client.post(URL, json=donnees, headers=entete).status_code == 422


def test_liste_triee_par_nom(db, client):
    admin, entete = preparer_admin(db, client)
    for nom, tel in [("Zoe", "710000001"), ("Alice", "710000002")]:
        donnees = dict(NOUVEAU)
        donnees["nom_complet"] = nom
        donnees["email"] = nom.lower() + "@atelier.sn"
        donnees["telephone"] = tel
        client.post(URL, json=donnees, headers=entete)
    noms = []
    for element in client.get(URL, headers=entete).json():
        noms.append(element["nom_complet"])
    assert noms == sorted(noms)


def test_detail_et_404(db, client):
    admin, entete = preparer_admin(db, client)
    assert client.get(URL + "/" + str(admin.id), headers=entete).status_code == 200
    assert client.get(URL + "/99999", headers=entete).status_code == 404


def test_modification_partielle(db, client):
    admin, entete = preparer_admin(db, client)
    cree = client.post(URL, json=NOUVEAU, headers=entete).json()
    reponse = client.patch(
        URL + "/" + str(cree["id"]),
        json={"role": "tailleur", "actif": False},
        headers=entete,
    )
    assert reponse.status_code == 200
    assert reponse.json()["role"] == "tailleur"
    assert reponse.json()["actif"] is False
    assert reponse.json()["nom_complet"] == "Nouveau Compte"


def test_changement_de_mot_de_passe(db, client):
    admin, entete = preparer_admin(db, client)
    cree = client.post(URL, json=NOUVEAU, headers=entete).json()
    client.patch(
        URL + "/" + str(cree["id"]), json={"mot_de_passe": "nouveaumdp123"}, headers=entete
    )
    reponse = client.post(
        "/api/v1/auth/login",
        data={"username": "nouveau@atelier.sn", "password": "nouveaumdp123"},
    )
    assert reponse.status_code == 200


def test_rg24_admin_ne_peut_pas_se_desactiver(db, client):
    admin, entete = preparer_admin(db, client)
    reponse = client.patch(URL + "/" + str(admin.id), json={"actif": False}, headers=entete)
    assert reponse.status_code == 409


def test_rg24_admin_ne_peut_pas_changer_son_role(db, client):
    admin, entete = preparer_admin(db, client)
    reponse = client.patch(URL + "/" + str(admin.id), json={"role": "accueil"}, headers=entete)
    assert reponse.status_code == 409


def test_rg24_admin_peut_modifier_son_nom(db, client):
    admin, entete = preparer_admin(db, client)
    reponse = client.patch(URL + "/" + str(admin.id), json={"nom_complet": "Nouveau"}, headers=entete)
    assert reponse.status_code == 200


def test_accueil_et_tailleur_403(db, client):
    creer_utilisateur(db, "accueil", "accueil@test.sn", "700000002")
    creer_utilisateur(db, "tailleur", "tailleur@test.sn", "700000003")
    for identifiant in ["accueil@test.sn", "tailleur@test.sn"]:
        entete = entete_auth(client, identifiant)
        assert client.get(URL, headers=entete).status_code == 403
        assert client.post(URL, json=NOUVEAU, headers=entete).status_code == 403
        assert client.get(URL + "/1", headers=entete).status_code == 403
        assert client.patch(URL + "/1", json={"actif": False}, headers=entete).status_code == 403


def test_sans_jeton_401(client):
    assert client.get(URL).status_code == 401
    assert client.post(URL, json=NOUVEAU).status_code == 401
