from datetime import date, timedelta

from sqlalchemy import select

from app.models import Commande, Utilisateur
from tests.utils import (
    creer_client_bd,
    creer_commande_api,
    creer_mesure_bd,
    creer_prestation_bd,
    entete_pour_role,
)

URL = "/api/v1/commandes"


def preparer(db, client):
    """Un client, deux prestations (délais 10 et 4 jours) et un compte accueil."""
    entete = entete_pour_role(db, client, "accueil")
    fatou = creer_client_bd(db)
    boubou = creer_prestation_bd(db, "Boubou", 35000, 10)
    pantalon = creer_prestation_bd(db, "Pantalon", 12000, 4)
    return entete, fatou, boubou, pantalon


def trouver_tailleur(db, client):
    entete_pour_role(db, client, "tailleur")
    return db.scalars(select(Utilisateur).where(Utilisateur.role == "tailleur")).first()


def test_creation_numero_montants_et_date_prevue(db, client):
    entete, fatou, boubou, pantalon = preparer(db, client)
    lignes = [
        {"type_vetement_id": boubou.id, "quantite": 2},
        {"type_vetement_id": pantalon.id, "quantite": 1, "prix_unitaire": 10000},
    ]
    reponse = creer_commande_api(client, entete, fatou.id, lignes, remise=5000)
    assert reponse.status_code == 201
    corps = reponse.json()

    # RG5 : numéro
    assert corps["numero"] == "CMD-" + str(date.today().year) + "-" + str(corps["id"]).zfill(5)
    assert corps["statut"] == "en_attente"
    # RG6 : prix par défaut du catalogue, prix négocié respecté
    assert corps["lignes"][0]["prix_unitaire"] == 35000
    assert corps["lignes"][0]["sous_total"] == 70000
    assert corps["lignes"][0]["type_vetement_nom"] == "Boubou"
    assert corps["lignes"][1]["prix_unitaire"] == 10000
    # RG7 : total = 70000 + 10000 - 5000
    assert corps["montant_total"] == 75000
    assert corps["montant_paye"] == 0
    assert corps["solde"] == 75000
    # RG8 : date commande + plus long délai (10 jours)
    assert corps["date_commande"] == date.today().isoformat()
    assert corps["date_livraison_prevue"] == (date.today() + timedelta(days=10)).isoformat()
    assert corps["en_retard"] is False
    assert corps["paiements"] == []
    assert corps["livraison"] is None


def test_seul_l_accueil_et_l_admin_creent_une_commande(db, client):
    entete, fatou, boubou, pantalon = preparer(db, client)
    lignes = [{"type_vetement_id": boubou.id, "quantite": 1}]
    entete_tailleur = entete_pour_role(db, client, "tailleur")
    assert creer_commande_api(client, entete_tailleur, fatou.id, lignes).status_code == 403
    entete_admin = entete_pour_role(db, client, "admin")
    assert creer_commande_api(client, entete_admin, fatou.id, lignes).status_code == 201
    assert client.post(URL, json={}).status_code == 401


def test_validations_de_creation(db, client):
    entete, fatou, boubou, pantalon = preparer(db, client)
    ligne = {"type_vetement_id": boubou.id, "quantite": 1}
    assert creer_commande_api(client, entete, fatou.id, []).status_code == 422
    quantite_nulle = [{"type_vetement_id": boubou.id, "quantite": 0}]
    assert creer_commande_api(client, entete, fatou.id, quantite_nulle).status_code == 422
    assert creer_commande_api(client, entete, fatou.id, [ligne], remise=-1).status_code == 422
    assert creer_commande_api(client, entete, 99999, [ligne]).status_code == 404
    inconnue = [{"type_vetement_id": 99999, "quantite": 1}]
    assert creer_commande_api(client, entete, fatou.id, inconnue).status_code == 404


def test_rg6_prestation_inactive_422(db, client):
    entete, fatou, boubou, pantalon = preparer(db, client)
    ancienne = creer_prestation_bd(db, "Ancienne", 5000, 3, actif=False)
    lignes = [{"type_vetement_id": ancienne.id, "quantite": 1}]
    assert creer_commande_api(client, entete, fatou.id, lignes).status_code == 422


def test_rg7_remise_superieure_a_la_somme_422(db, client):
    entete, fatou, boubou, pantalon = preparer(db, client)
    lignes = [{"type_vetement_id": pantalon.id, "quantite": 1}]
    assert creer_commande_api(client, entete, fatou.id, lignes, remise=12001).status_code == 422
    assert creer_commande_api(client, entete, fatou.id, lignes, remise=12000).status_code == 201


def test_rg8_date_prevue_explicite(db, client):
    entete, fatou, boubou, pantalon = preparer(db, client)
    lignes = [{"type_vetement_id": boubou.id, "quantite": 1}]
    hier = (date.today() - timedelta(days=1)).isoformat()
    reponse = creer_commande_api(client, entete, fatou.id, lignes, date_livraison_prevue=hier)
    assert reponse.status_code == 422
    dans_3_jours = (date.today() + timedelta(days=3)).isoformat()
    reponse = creer_commande_api(
        client, entete, fatou.id, lignes, date_livraison_prevue=dans_3_jours
    )
    assert reponse.status_code == 201
    assert reponse.json()["date_livraison_prevue"] == dans_3_jours


def test_rg9_dernieres_mesures_rattachees_automatiquement(db, client):
    entete, fatou, boubou, pantalon = preparer(db, client)
    tailleur = trouver_tailleur(db, client)
    ancienne = creer_mesure_bd(db, fatou, tailleur.id, date.today() - timedelta(days=60))
    recente = creer_mesure_bd(db, fatou, tailleur.id, date.today())
    lignes = [{"type_vetement_id": boubou.id, "quantite": 1}]

    corps = creer_commande_api(client, entete, fatou.id, lignes).json()
    assert corps["mesure_id"] == recente.id

    # Mesure choisie explicitement
    corps = creer_commande_api(client, entete, fatou.id, lignes, mesure_id=ancienne.id).json()
    assert corps["mesure_id"] == ancienne.id


def test_rg9_sans_mesures_mesure_id_vide(db, client):
    entete, fatou, boubou, pantalon = preparer(db, client)
    lignes = [{"type_vetement_id": boubou.id, "quantite": 1}]
    assert creer_commande_api(client, entete, fatou.id, lignes).json()["mesure_id"] is None


def test_rg9_mesure_d_un_autre_client_422(db, client):
    entete, fatou, boubou, pantalon = preparer(db, client)
    tailleur = trouver_tailleur(db, client)
    autre = creer_client_bd(db, telephone="780000000", nom="Ba", prenom="Moussa", genre="homme")
    mesure_autre = creer_mesure_bd(db, autre, tailleur.id)
    lignes = [{"type_vetement_id": boubou.id, "quantite": 1}]
    reponse = creer_commande_api(client, entete, fatou.id, lignes, mesure_id=mesure_autre.id)
    assert reponse.status_code == 422
    assert creer_commande_api(client, entete, fatou.id, lignes, mesure_id=99999).status_code == 422


def test_detail_et_404(db, client):
    entete, fatou, boubou, pantalon = preparer(db, client)
    corps = creer_commande_api(
        client, entete, fatou.id, [{"type_vetement_id": boubou.id, "quantite": 1}]
    ).json()
    assert client.get(URL + "/" + str(corps["id"]), headers=entete).status_code == 200
    assert client.get(URL + "/99999", headers=entete).status_code == 404


def test_lecture_ouverte_a_tous_les_roles(db, client):
    entete, fatou, boubou, pantalon = preparer(db, client)
    corps = creer_commande_api(
        client, entete, fatou.id, [{"type_vetement_id": boubou.id, "quantite": 1}]
    ).json()
    entete_tailleur = entete_pour_role(db, client, "tailleur")
    assert client.get(URL, headers=entete_tailleur).status_code == 200
    assert client.get(URL + "/" + str(corps["id"]), headers=entete_tailleur).status_code == 200
    assert client.get(URL).status_code == 401


def creer_trois_commandes(db, client):
    entete, fatou, boubou, pantalon = preparer(db, client)
    moussa = creer_client_bd(db, telephone="780000000", nom="Ba", prenom="Moussa", genre="homme")
    ligne_boubou = [{"type_vetement_id": boubou.id, "quantite": 1}]
    ligne_pantalon = [{"type_vetement_id": pantalon.id, "quantite": 1}]
    c1 = creer_commande_api(client, entete, fatou.id, ligne_boubou).json()
    c2 = creer_commande_api(client, entete, moussa.id, ligne_pantalon).json()
    c3 = creer_commande_api(client, entete, fatou.id, ligne_pantalon).json()
    return entete, fatou, moussa, c1, c2, c3


def test_liste_paginee_recente_d_abord_avec_champs_calcules(db, client):
    entete, fatou, moussa, c1, c2, c3 = creer_trois_commandes(db, client)
    corps = client.get(URL, headers=entete).json()
    assert corps["total"] == 3
    assert corps["limit"] == 20
    assert corps["offset"] == 0
    assert corps["items"][0]["id"] == c3["id"]
    assert corps["items"][2]["id"] == c1["id"]
    milieu = corps["items"][1]
    assert milieu["client_nom"] == "Moussa Ba"
    assert milieu["solde"] == 12000
    assert milieu["en_retard"] is False

    page = client.get(URL + "?limit=1&offset=1", headers=entete).json()
    assert page["total"] == 3
    assert len(page["items"]) == 1
    assert page["items"][0]["id"] == c2["id"]


def test_filtres_de_la_liste(db, client):
    entete, fatou, moussa, c1, c2, c3 = creer_trois_commandes(db, client)
    assert client.get(URL + "?client_id=" + str(fatou.id), headers=entete).json()["total"] == 2
    assert client.get(URL + "?statut=en_attente", headers=entete).json()["total"] == 3
    assert client.get(URL + "?statut=livree", headers=entete).json()["total"] == 0
    assert client.get(URL + "?numero=" + c2["numero"], headers=entete).json()["total"] == 1
    aujourdhui = date.today().isoformat()
    demain = (date.today() + timedelta(days=1)).isoformat()
    assert client.get(URL + "?date_min=" + demain, headers=entete).json()["total"] == 0
    assert client.get(URL + "?date_max=" + aujourdhui, headers=entete).json()["total"] == 3
    assert client.get(URL + "?statut=inconnu", headers=entete).status_code == 422


def test_rg11_filtre_et_champ_en_retard(db, client):
    entete, fatou, moussa, c1, c2, c3 = creer_trois_commandes(db, client)
    commande = db.get(Commande, c1["id"])
    commande.date_livraison_prevue = date.today() - timedelta(days=2)
    db.commit()

    en_retard = client.get(URL + "?en_retard=true", headers=entete).json()
    assert en_retard["total"] == 1
    assert en_retard["items"][0]["id"] == c1["id"]
    assert en_retard["items"][0]["en_retard"] is True
    assert client.get(URL + "?en_retard=false", headers=entete).json()["total"] == 2

    # Une commande annulée n'est jamais en retard
    commande = db.get(Commande, c1["id"])
    commande.statut = "annulee"
    db.commit()
    assert client.get(URL + "?en_retard=true", headers=entete).json()["total"] == 0


def test_commandes_d_un_client(db, client):
    entete, fatou, moussa, c1, c2, c3 = creer_trois_commandes(db, client)
    corps = client.get("/api/v1/clients/" + str(fatou.id) + "/commandes", headers=entete).json()
    assert corps["total"] == 2
    assert corps["items"][0]["id"] == c3["id"]
    assert client.get("/api/v1/clients/99999/commandes", headers=entete).status_code == 404


def test_resume_client_exclut_les_annulees(db, client):
    entete, fatou, moussa, c1, c2, c3 = creer_trois_commandes(db, client)
    corps = client.get("/api/v1/clients/" + str(fatou.id) + "/resume", headers=entete).json()
    assert corps["nb_commandes"] == 2
    assert corps["chiffre_affaires"] == 35000 + 12000
    assert corps["total_paye"] == 0
    assert corps["solde_du"] == 47000
    assert corps["derniere_commande"] == date.today().isoformat()
    assert corps["a_des_mesures"] is False

    commande = db.get(Commande, c1["id"])
    commande.statut = "annulee"
    db.commit()
    corps = client.get("/api/v1/clients/" + str(fatou.id) + "/resume", headers=entete).json()
    assert corps["nb_commandes"] == 1
    assert corps["chiffre_affaires"] == 12000
    assert client.get("/api/v1/clients/99999/resume", headers=entete).status_code == 404


def test_resume_client_sans_commande(db, client):
    entete = entete_pour_role(db, client, "accueil")
    fatou = creer_client_bd(db)
    corps = client.get("/api/v1/clients/" + str(fatou.id) + "/resume", headers=entete).json()
    assert corps["nb_commandes"] == 0
    assert corps["derniere_commande"] is None


def test_rg4_client_avec_commandes_non_supprimable(db, client):
    entete, fatou, boubou, pantalon = preparer(db, client)
    creer_commande_api(client, entete, fatou.id, [{"type_vetement_id": boubou.id, "quantite": 1}])
    entete_admin = entete_pour_role(db, client, "admin")
    reponse = client.delete("/api/v1/clients/" + str(fatou.id), headers=entete_admin)
    assert reponse.status_code == 409


def test_rg4_mesure_utilisee_par_une_commande_non_supprimable(db, client):
    entete, fatou, boubou, pantalon = preparer(db, client)
    entete_tailleur = entete_pour_role(db, client, "tailleur")
    prise = client.post(
        "/api/v1/clients/" + str(fatou.id) + "/mesures",
        json={"tour_cou": 38},
        headers=entete_tailleur,
    ).json()
    corps = creer_commande_api(
        client, entete, fatou.id, [{"type_vetement_id": boubou.id, "quantite": 1}]
    ).json()
    assert corps["mesure_id"] == prise["id"]
    reponse = client.delete("/api/v1/mesures/" + str(prise["id"]), headers=entete_tailleur)
    assert reponse.status_code == 409
