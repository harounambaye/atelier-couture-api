from tests.utils import entete_pour_role

URL = "/api/v1/catalogue"

BOUBOU = {"nom": "Boubou", "description": "Boubou homme", "prix_base": 35000, "delai_jours": 10}


def test_creation_admin_201(db, client):
    entete = entete_pour_role(db, client, "admin")
    reponse = client.post(URL, json=BOUBOU, headers=entete)
    assert reponse.status_code == 201
    assert reponse.json()["actif"] is True
    assert reponse.json()["prix_base"] == 35000


def test_nom_existant_409(db, client):
    entete = entete_pour_role(db, client, "admin")
    client.post(URL, json=BOUBOU, headers=entete)
    assert client.post(URL, json=BOUBOU, headers=entete).status_code == 409


def test_donnees_invalides_422(db, client):
    entete = entete_pour_role(db, client, "admin")
    mauvais_prix = dict(BOUBOU)
    mauvais_prix["prix_base"] = -5
    assert client.post(URL, json=mauvais_prix, headers=entete).status_code == 422
    sans_delai = {"nom": "Robe", "prix_base": 1000}
    assert client.post(URL, json=sans_delai, headers=entete).status_code == 422


def test_creation_et_modification_interdites_aux_autres_roles(db, client):
    entete_admin = entete_pour_role(db, client, "admin")
    cree = client.post(URL, json=BOUBOU, headers=entete_admin).json()
    for role in ["accueil", "tailleur"]:
        entete = entete_pour_role(db, client, role)
        assert client.post(URL, json=BOUBOU, headers=entete).status_code == 403
        reponse = client.patch(URL + "/" + str(cree["id"]), json={"prix_base": 1}, headers=entete)
        assert reponse.status_code == 403


def test_lecture_ouverte_a_tous_les_roles(db, client):
    entete_admin = entete_pour_role(db, client, "admin")
    cree = client.post(URL, json=BOUBOU, headers=entete_admin).json()
    for role in ["accueil", "tailleur"]:
        entete = entete_pour_role(db, client, role)
        assert client.get(URL, headers=entete).status_code == 200
        assert client.get(URL + "/" + str(cree["id"]), headers=entete).status_code == 200


def test_sans_jeton_401(client):
    assert client.get(URL).status_code == 401


def test_detail_404(db, client):
    entete = entete_pour_role(db, client, "accueil")
    assert client.get(URL + "/99999", headers=entete).status_code == 404


def test_liste_triee_par_nom_et_actifs_seulement(db, client):
    entete = entete_pour_role(db, client, "admin")
    for nom in ["Robe", "Chemise", "Pantalon"]:
        donnees = dict(BOUBOU)
        donnees["nom"] = nom
        client.post(URL, json=donnees, headers=entete)
    liste = client.get(URL, headers=entete).json()
    noms = []
    for element in liste:
        noms.append(element["nom"])
    assert noms == ["Chemise", "Pantalon", "Robe"]

    # On désactive la robe
    id_robe = liste[2]["id"]
    client.patch(URL + "/" + str(id_robe), json={"actif": False}, headers=entete)
    assert len(client.get(URL, headers=entete).json()) == 2
    assert len(client.get(URL + "?actifs_seulement=false", headers=entete).json()) == 3


def test_modification_partielle(db, client):
    entete = entete_pour_role(db, client, "admin")
    cree = client.post(URL, json=BOUBOU, headers=entete).json()
    reponse = client.patch(
        URL + "/" + str(cree["id"]), json={"prix_base": 40000, "delai_jours": 12}, headers=entete
    )
    assert reponse.status_code == 200
    assert reponse.json()["prix_base"] == 40000
    assert reponse.json()["delai_jours"] == 12
    assert reponse.json()["nom"] == "Boubou"


def test_modification_vers_un_nom_existant_409(db, client):
    entete = entete_pour_role(db, client, "admin")
    client.post(URL, json=BOUBOU, headers=entete)
    robe = dict(BOUBOU)
    robe["nom"] = "Robe"
    cree = client.post(URL, json=robe, headers=entete).json()
    reponse = client.patch(URL + "/" + str(cree["id"]), json={"nom": "Boubou"}, headers=entete)
    assert reponse.status_code == 409
