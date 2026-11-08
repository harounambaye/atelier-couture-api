from tests.utils import entete_pour_role

URL = "/api/v1/clients"

FATOU = {"nom": "Diop", "prenom": "Fatou", "telephone": "77 123 45 67", "genre": "femme"}


def creer_client_api(client, entete, **changements):
    donnees = dict(FATOU)
    donnees.update(changements)
    return client.post(URL, json=donnees, headers=entete)


def test_creation_201_et_normalisation_rg1(db, client):
    entete = entete_pour_role(db, client, "accueil")
    reponse = creer_client_api(client, entete)
    assert reponse.status_code == 201
    assert reponse.json()["telephone"] == "771234567"


def test_doublon_telephone_409_meme_avec_autre_format(db, client):
    entete = entete_pour_role(db, client, "accueil")
    creer_client_api(client, entete)
    reponse = creer_client_api(client, entete, nom="Autre", telephone="771234567")
    assert reponse.status_code == 409


def test_telephone_invalide_422(db, client):
    entete = entete_pour_role(db, client, "accueil")
    assert creer_client_api(client, entete, telephone="12ab").status_code == 422
    assert creer_client_api(client, entete, telephone="123").status_code == 422


def test_genre_invalide_422(db, client):
    entete = entete_pour_role(db, client, "accueil")
    assert creer_client_api(client, entete, genre="robot").status_code == 422


def test_tous_les_roles_peuvent_creer_et_lire(db, client):
    for role in ["admin", "accueil", "tailleur"]:
        entete = entete_pour_role(db, client, role)
        reponse = creer_client_api(client, entete, telephone="7" + str(len(role)) + "0000000")
        assert reponse.status_code == 201
        assert client.get(URL, headers=entete).status_code == 200


def test_sans_jeton_401(client):
    assert client.get(URL).status_code == 401


def test_detail_et_404(db, client):
    entete = entete_pour_role(db, client, "accueil")
    cree = creer_client_api(client, entete).json()
    assert client.get(URL + "/" + str(cree["id"]), headers=entete).status_code == 200
    assert client.get(URL + "/99999", headers=entete).status_code == 404


def test_liste_paginee_triee_nom_puis_prenom(db, client):
    entete = entete_pour_role(db, client, "accueil")
    creer_client_api(client, entete, nom="Sow", prenom="Awa", telephone="710000001")
    creer_client_api(client, entete, nom="Ba", prenom="Zeynab", telephone="710000002")
    creer_client_api(client, entete, nom="Ba", prenom="Aminata", telephone="710000003")
    corps = client.get(URL, headers=entete).json()
    assert corps["total"] == 3
    assert corps["limit"] == 20
    assert corps["offset"] == 0
    ordre = []
    for element in corps["items"]:
        ordre.append(element["nom"] + " " + element["prenom"])
    assert ordre == ["Ba Aminata", "Ba Zeynab", "Sow Awa"]


def test_pagination_limit_et_offset(db, client):
    entete = entete_pour_role(db, client, "accueil")
    for i in range(5):
        creer_client_api(client, entete, nom="Nom" + str(i), telephone="72000000" + str(i))
    corps = client.get(URL + "?limit=2&offset=2", headers=entete).json()
    assert corps["total"] == 5
    assert len(corps["items"]) == 2
    assert corps["items"][0]["nom"] == "Nom2"
    assert client.get(URL + "?limit=101", headers=entete).status_code == 422


def test_recherche_q_nom_prenom_telephone(db, client):
    entete = entete_pour_role(db, client, "accueil")
    creer_client_api(client, entete)
    creer_client_api(client, entete, nom="Ndiaye", prenom="Moussa", telephone="780000000", genre="homme")
    assert client.get(URL + "?q=dio", headers=entete).json()["total"] == 1
    assert client.get(URL + "?q=MOUSSA", headers=entete).json()["total"] == 1
    assert client.get(URL + "?q=78000", headers=entete).json()["total"] == 1
    assert client.get(URL + "?q=77 123", headers=entete).json()["total"] == 1
    assert client.get(URL + "?q=zzz", headers=entete).json()["total"] == 0


def test_recherche_q_trop_courte_422(db, client):
    entete = entete_pour_role(db, client, "accueil")
    assert client.get(URL + "?q=a", headers=entete).status_code == 422


def test_filtre_genre(db, client):
    entete = entete_pour_role(db, client, "accueil")
    creer_client_api(client, entete)
    creer_client_api(client, entete, nom="Ndiaye", telephone="780000000", genre="homme")
    corps = client.get(URL + "?genre=homme", headers=entete).json()
    assert corps["total"] == 1
    assert corps["items"][0]["nom"] == "Ndiaye"


def test_modification_partielle(db, client):
    entete = entete_pour_role(db, client, "accueil")
    cree = creer_client_api(client, entete).json()
    reponse = client.patch(
        URL + "/" + str(cree["id"]), json={"adresse": "Dakar"}, headers=entete
    )
    assert reponse.status_code == 200
    assert reponse.json()["adresse"] == "Dakar"
    assert reponse.json()["nom"] == "Diop"


def test_garder_son_propre_numero_n_est_pas_un_doublon(db, client):
    entete = entete_pour_role(db, client, "accueil")
    cree = creer_client_api(client, entete).json()
    reponse = client.patch(
        URL + "/" + str(cree["id"]), json={"telephone": "77 123 45 67"}, headers=entete
    )
    assert reponse.status_code == 200


def test_modifier_vers_numero_existant_409(db, client):
    entete = entete_pour_role(db, client, "accueil")
    creer_client_api(client, entete)
    autre = creer_client_api(client, entete, nom="Autre", telephone="780000000").json()
    reponse = client.patch(
        URL + "/" + str(autre["id"]), json={"telephone": "771234567"}, headers=entete
    )
    assert reponse.status_code == 409


def test_nom_prenom_telephone_non_vidables_422(db, client):
    entete = entete_pour_role(db, client, "accueil")
    cree = creer_client_api(client, entete).json()
    adresse = URL + "/" + str(cree["id"])
    assert client.patch(adresse, json={"nom": ""}, headers=entete).status_code == 422
    assert client.patch(adresse, json={"prenom": None}, headers=entete).status_code == 422
    assert client.patch(adresse, json={"telephone": ""}, headers=entete).status_code == 422


def test_suppression_reservee_a_l_admin(db, client):
    entete_accueil = entete_pour_role(db, client, "accueil")
    entete_admin = entete_pour_role(db, client, "admin")
    cree = creer_client_api(client, entete_accueil).json()
    adresse = URL + "/" + str(cree["id"])
    assert client.delete(adresse, headers=entete_accueil).status_code == 403
    assert client.delete(adresse, headers=entete_admin).status_code == 204
    assert client.get(adresse, headers=entete_admin).status_code == 404
    assert client.delete(adresse, headers=entete_admin).status_code == 404
