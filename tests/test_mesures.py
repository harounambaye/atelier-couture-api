from datetime import date, timedelta

from tests.utils import entete_pour_role

CHAMPS_MESURES = [
    "taille_cm", "tour_cou", "carrure_dos", "longueur_epaule", "tour_poitrine",
    "tour_taille", "tour_bassin", "longueur_manche", "tour_bras", "tour_poignet",
    "longueur_dos", "longueur_haut", "longueur_pantalon", "tour_cuisse", "tour_genou",
    "bas_pantalon", "entrejambe", "longueur_robe",
]


def creer_client_api(client, entete, telephone="771234567"):
    donnees = {"nom": "Diop", "prenom": "Fatou", "telephone": telephone, "genre": "femme"}
    return client.post("/api/v1/clients", json=donnees, headers=entete).json()


def url_mesures(client_id):
    return "/api/v1/clients/" + str(client_id) + "/mesures"


def test_prise_de_mesures_201_par_le_tailleur(db, client):
    entete_tailleur = entete_pour_role(db, client, "tailleur")
    fatou = creer_client_api(client, entete_tailleur)
    reponse = client.post(
        url_mesures(fatou["id"]),
        json={"tour_poitrine": 92.5, "tour_taille": 70},
        headers=entete_tailleur,
    )
    assert reponse.status_code == 201
    corps = reponse.json()
    assert corps["tour_poitrine"] == 92.5
    assert corps["tour_cou"] is None
    assert corps["date_prise"] == date.today().isoformat()
    assert corps["prise_par_id"] > 0
    assert corps["client_id"] == fatou["id"]


def test_les_18_champs_sont_acceptes(db, client):
    entete = entete_pour_role(db, client, "tailleur")
    fatou = creer_client_api(client, entete)
    donnees = {}
    for champ in CHAMPS_MESURES:
        donnees[champ] = 50
    reponse = client.post(url_mesures(fatou["id"]), json=donnees, headers=entete)
    assert reponse.status_code == 201
    for champ in CHAMPS_MESURES:
        assert reponse.json()[champ] == 50


def test_accueil_ne_peut_pas_prendre_les_mesures_403(db, client):
    entete_accueil = entete_pour_role(db, client, "accueil")
    fatou = creer_client_api(client, entete_accueil)
    reponse = client.post(url_mesures(fatou["id"]), json={"tour_cou": 38}, headers=entete_accueil)
    assert reponse.status_code == 403


def test_admin_peut_prendre_les_mesures(db, client):
    entete = entete_pour_role(db, client, "admin")
    fatou = creer_client_api(client, entete)
    reponse = client.post(url_mesures(fatou["id"]), json={"tour_cou": 38}, headers=entete)
    assert reponse.status_code == 201


def test_rg2_au_moins_une_mesure_422(db, client):
    entete = entete_pour_role(db, client, "tailleur")
    fatou = creer_client_api(client, entete)
    assert client.post(url_mesures(fatou["id"]), json={}, headers=entete).status_code == 422
    reponse = client.post(url_mesures(fatou["id"]), json={"notes": "rien"}, headers=entete)
    assert reponse.status_code == 422


def test_rg2_valeurs_entre_0_exclu_et_300(db, client):
    entete = entete_pour_role(db, client, "tailleur")
    fatou = creer_client_api(client, entete)
    url = url_mesures(fatou["id"])
    assert client.post(url, json={"tour_cou": 0}, headers=entete).status_code == 422
    assert client.post(url, json={"tour_cou": -4}, headers=entete).status_code == 422
    assert client.post(url, json={"tour_cou": 300.5}, headers=entete).status_code == 422
    assert client.post(url, json={"tour_cou": 300}, headers=entete).status_code == 201


def test_client_inconnu_404(db, client):
    entete = entete_pour_role(db, client, "tailleur")
    assert client.post(url_mesures(999), json={"tour_cou": 38}, headers=entete).status_code == 404
    assert client.get(url_mesures(999), headers=entete).status_code == 404
    assert client.get(url_mesures(999) + "/derniere", headers=entete).status_code == 404


def test_rg3_historique_conserve_et_derniere_mesure(db, client):
    entete = entete_pour_role(db, client, "tailleur")
    fatou = creer_client_api(client, entete)
    url = url_mesures(fatou["id"])
    hier = (date.today() - timedelta(days=30)).isoformat()
    client.post(url, json={"tour_cou": 36, "date_prise": hier}, headers=entete)
    client.post(url, json={"tour_cou": 38}, headers=entete)

    historique = client.get(url, headers=entete).json()
    assert len(historique) == 2
    assert historique[0]["tour_cou"] == 38  # la plus récente d'abord
    assert historique[1]["tour_cou"] == 36

    derniere = client.get(url + "/derniere", headers=entete).json()
    assert derniere["tour_cou"] == 38


def test_derniere_404_si_aucune_mesure(db, client):
    entete = entete_pour_role(db, client, "tailleur")
    fatou = creer_client_api(client, entete)
    assert client.get(url_mesures(fatou["id"]) + "/derniere", headers=entete).status_code == 404


def test_lecture_ouverte_a_tous_les_roles(db, client):
    entete_tailleur = entete_pour_role(db, client, "tailleur")
    fatou = creer_client_api(client, entete_tailleur)
    mesure = client.post(
        url_mesures(fatou["id"]), json={"tour_cou": 38}, headers=entete_tailleur
    ).json()
    entete_accueil = entete_pour_role(db, client, "accueil")
    assert client.get(url_mesures(fatou["id"]), headers=entete_accueil).status_code == 200
    assert client.get("/api/v1/mesures/" + str(mesure["id"]), headers=entete_accueil).status_code == 200
    assert client.get("/api/v1/mesures/99999", headers=entete_accueil).status_code == 404


def test_sans_jeton_401(client):
    assert client.get("/api/v1/mesures/1").status_code == 401
    assert client.post(url_mesures(1), json={"tour_cou": 38}).status_code == 401


def test_correction_partielle_par_le_tailleur(db, client):
    entete = entete_pour_role(db, client, "tailleur")
    fatou = creer_client_api(client, entete)
    mesure = client.post(
        url_mesures(fatou["id"]), json={"tour_cou": 38, "tour_taille": 70}, headers=entete
    ).json()
    adresse = "/api/v1/mesures/" + str(mesure["id"])
    reponse = client.patch(adresse, json={"tour_cou": 39}, headers=entete)
    assert reponse.status_code == 200
    assert reponse.json()["tour_cou"] == 39
    assert reponse.json()["tour_taille"] == 70


def test_correction_accueil_403(db, client):
    entete_tailleur = entete_pour_role(db, client, "tailleur")
    fatou = creer_client_api(client, entete_tailleur)
    mesure = client.post(
        url_mesures(fatou["id"]), json={"tour_cou": 38}, headers=entete_tailleur
    ).json()
    entete_accueil = entete_pour_role(db, client, "accueil")
    adresse = "/api/v1/mesures/" + str(mesure["id"])
    assert client.patch(adresse, json={"tour_cou": 39}, headers=entete_accueil).status_code == 403
    assert client.delete(adresse, headers=entete_accueil).status_code == 403


def test_correction_qui_supprimerait_toutes_les_mesures_422(db, client):
    entete = entete_pour_role(db, client, "tailleur")
    fatou = creer_client_api(client, entete)
    mesure = client.post(url_mesures(fatou["id"]), json={"tour_cou": 38}, headers=entete).json()
    adresse = "/api/v1/mesures/" + str(mesure["id"])
    assert client.patch(adresse, json={"tour_cou": None}, headers=entete).status_code == 422
    # La prise est inchangée
    assert client.get(adresse, headers=entete).json()["tour_cou"] == 38


def test_correction_peut_retirer_une_mesure_s_il_en_reste(db, client):
    entete = entete_pour_role(db, client, "tailleur")
    fatou = creer_client_api(client, entete)
    mesure = client.post(
        url_mesures(fatou["id"]), json={"tour_cou": 38, "tour_taille": 70}, headers=entete
    ).json()
    adresse = "/api/v1/mesures/" + str(mesure["id"])
    reponse = client.patch(adresse, json={"tour_taille": None}, headers=entete)
    assert reponse.status_code == 200
    assert reponse.json()["tour_taille"] is None


def test_correction_valeur_invalide_422(db, client):
    entete = entete_pour_role(db, client, "tailleur")
    fatou = creer_client_api(client, entete)
    mesure = client.post(url_mesures(fatou["id"]), json={"tour_cou": 38}, headers=entete).json()
    adresse = "/api/v1/mesures/" + str(mesure["id"])
    assert client.patch(adresse, json={"tour_cou": 400}, headers=entete).status_code == 422


def test_suppression_204_puis_404(db, client):
    entete = entete_pour_role(db, client, "tailleur")
    fatou = creer_client_api(client, entete)
    mesure = client.post(url_mesures(fatou["id"]), json={"tour_cou": 38}, headers=entete).json()
    adresse = "/api/v1/mesures/" + str(mesure["id"])
    assert client.delete(adresse, headers=entete).status_code == 204
    assert client.get(adresse, headers=entete).status_code == 404


def test_supprimer_un_client_supprime_ses_mesures(db, client):
    entete_admin = entete_pour_role(db, client, "admin")
    fatou = creer_client_api(client, entete_admin)
    mesure = client.post(
        url_mesures(fatou["id"]), json={"tour_cou": 38}, headers=entete_admin
    ).json()
    assert client.delete("/api/v1/clients/" + str(fatou["id"]), headers=entete_admin).status_code == 204
    assert client.get("/api/v1/mesures/" + str(mesure["id"]), headers=entete_admin).status_code == 404
