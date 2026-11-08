from datetime import date, timedelta

from sqlalchemy import select

from app.models import Commande, Paiement, Utilisateur
from tests.utils import (
    creer_client_bd,
    creer_commande_api,
    creer_prestation_bd,
    entete_pour_role,
)

URL = "/api/v1/statistiques"

TOUS_LES_STATUTS = [
    "en_attente", "en_coupe", "en_couture", "essayage",
    "retouches", "terminee", "livree", "annulee",
]


def preparer_donnees(db, client):
    """
    C1 Fatou : 2 boubous + 1 pantalon, remise 2 000 -> 80 000, 30 000 payés, terminée,
               livraison planifiée aujourd'hui
    C2 Moussa : 1 pantalon -> 12 000, en retard
    C3 Fatou : 1 boubou -> annulée
    C4 Fatou : 1 boubou -> 35 000, commande d'il y a 40 jours, 10 000 payés ce jour-là
    """
    entete_accueil = entete_pour_role(db, client, "accueil")
    entete_admin = entete_pour_role(db, client, "admin")
    fatou = creer_client_bd(db)
    moussa = creer_client_bd(db, telephone="780000000", nom="Ba", prenom="Moussa", genre="homme")
    boubou = creer_prestation_bd(db, "Boubou", 35000, 10)
    pantalon = creer_prestation_bd(db, "Pantalon", 12000, 4)

    ligne_boubou = {"type_vetement_id": boubou.id, "quantite": 1}
    ligne_pantalon = {"type_vetement_id": pantalon.id, "quantite": 1}
    c1 = creer_commande_api(
        client, entete_accueil, fatou.id,
        [{"type_vetement_id": boubou.id, "quantite": 2}, ligne_pantalon], remise=2000,
    ).json()
    c2 = creer_commande_api(client, entete_accueil, moussa.id, [ligne_pantalon]).json()
    c3 = creer_commande_api(client, entete_accueil, fatou.id, [ligne_boubou]).json()
    c4 = creer_commande_api(client, entete_accueil, fatou.id, [ligne_boubou]).json()

    client.post(
        "/api/v1/commandes/" + str(c1["id"]) + "/paiements",
        json={"montant": 30000, "mode": "wave"},
        headers=entete_accueil,
    )
    client.put(
        "/api/v1/commandes/" + str(c1["id"]) + "/livraison",
        json={"mode": "retrait_atelier", "date_prevue": date.today().isoformat()},
        headers=entete_accueil,
    )

    # Ajustements directs en base pour fabriquer des situations passées
    ancien = date.today() - timedelta(days=40)
    utilisateur = db.scalars(select(Utilisateur)).first()
    db.get(Commande, c1["id"]).statut = "terminee"
    db.get(Commande, c2["id"]).date_livraison_prevue = date.today() - timedelta(days=1)
    db.get(Commande, c3["id"]).statut = "annulee"
    commande4 = db.get(Commande, c4["id"])
    commande4.date_commande = ancien
    commande4.montant_paye = 10000
    db.add(
        Paiement(
            commande_id=c4["id"], montant=10000, mode="especes",
            date_paiement=ancien, enregistre_par_id=utilisateur.id,
        )
    )
    db.commit()
    return entete_admin, entete_accueil, ancien


def test_tableau_de_bord(db, client):
    entete_admin, _, _ = preparer_donnees(db, client)
    corps = client.get(URL + "/tableau-de-bord", headers=entete_admin).json()
    assert corps["chiffre_affaires_mois"] == 80000 + 12000
    assert corps["encaisse_mois"] == 30000
    assert corps["nb_commandes_mois"] == 2
    # soldes : C1 50 000 + C2 12 000 + C4 25 000 (C3 annulée exclue)
    assert corps["reste_a_encaisser"] == 87000
    assert corps["nb_commandes_en_retard"] == 1
    assert corps["commandes_pretes_a_livrer"] == 1
    assert corps["livraisons_du_jour"] == 1


def test_tableau_de_bord_contient_tous_les_statuts_meme_a_zero(db, client):
    entete_admin, _, _ = preparer_donnees(db, client)
    par_statut = client.get(URL + "/tableau-de-bord", headers=entete_admin).json()["commandes_par_statut"]
    assert sorted(par_statut.keys()) == sorted(TOUS_LES_STATUTS)
    assert par_statut["en_attente"] == 2
    assert par_statut["terminee"] == 1
    assert par_statut["annulee"] == 1
    assert par_statut["livree"] == 0
    assert par_statut["en_coupe"] == 0


def test_tableau_de_bord_sans_aucune_donnee(db, client):
    entete_admin = entete_pour_role(db, client, "admin")
    corps = client.get(URL + "/tableau-de-bord", headers=entete_admin).json()
    assert corps["chiffre_affaires_mois"] == 0
    assert corps["reste_a_encaisser"] == 0
    assert corps["nb_commandes_en_retard"] == 0
    assert len(corps["commandes_par_statut"]) == 8


def test_chiffre_affaires_par_jour_par_defaut_mois_courant(db, client):
    entete_admin, _, _ = preparer_donnees(db, client)
    corps = client.get(URL + "/chiffre-affaires", headers=entete_admin).json()
    assert corps["granularite"] == "jour"
    assert corps["date_debut"] == date.today().replace(day=1).isoformat()
    assert corps["date_fin"] == date.today().isoformat()
    assert len(corps["periodes"]) == 1
    jour = corps["periodes"][0]
    assert jour["periode"] == date.today().isoformat()
    assert jour["chiffre_affaires"] == 92000
    assert jour["encaissements"] == 30000
    assert jour["nb_commandes"] == 2


def test_chiffre_affaires_par_mois_sur_une_periode_large(db, client):
    entete_admin, _, ancien = preparer_donnees(db, client)
    debut = (date.today() - timedelta(days=60)).isoformat()
    corps = client.get(
        URL + "/chiffre-affaires?granularite=mois&date_debut=" + debut, headers=entete_admin
    ).json()
    cles = []
    for periode in corps["periodes"]:
        cles.append(periode["periode"])
    assert cles == [ancien.strftime("%Y-%m"), date.today().strftime("%Y-%m")]
    assert corps["periodes"][0]["chiffre_affaires"] == 35000
    assert corps["periodes"][0]["encaissements"] == 10000
    assert corps["periodes"][1]["chiffre_affaires"] == 92000


def test_chiffre_affaires_periode_sans_activite_et_dates_inversees(db, client):
    entete_admin, _, _ = preparer_donnees(db, client)
    adresse = URL + "/chiffre-affaires?date_debut=2020-01-01&date_fin=2020-01-31"
    assert client.get(adresse, headers=entete_admin).json()["periodes"] == []
    inversees = URL + "/chiffre-affaires?date_debut=2026-05-10&date_fin=2026-05-01"
    assert client.get(inversees, headers=entete_admin).status_code == 422
    assert client.get(URL + "/chiffre-affaires?granularite=annee", headers=entete_admin).status_code == 422


def test_types_vetement_quantites_et_ca_avant_remise(db, client):
    entete_admin, _, _ = preparer_donnees(db, client)
    corps = client.get(URL + "/types-vetement", headers=entete_admin).json()
    assert len(corps) == 2
    assert corps[0]["nom"] == "Boubou"
    assert corps[0]["quantite_vendue"] == 2  # la commande annulée est exclue
    assert corps[0]["chiffre_affaires_avant_remise"] == 70000  # avant la remise de 2 000
    assert corps[1]["nom"] == "Pantalon"
    assert corps[1]["quantite_vendue"] == 2
    assert corps[1]["chiffre_affaires_avant_remise"] == 24000

    debut = (date.today() - timedelta(days=60)).isoformat()
    large = client.get(URL + "/types-vetement?date_debut=" + debut, headers=entete_admin).json()
    assert large[0]["quantite_vendue"] == 3
    assert large[0]["chiffre_affaires_avant_remise"] == 105000


def test_top_clients(db, client):
    entete_admin, _, _ = preparer_donnees(db, client)
    corps = client.get(URL + "/top-clients", headers=entete_admin).json()
    assert len(corps) == 2
    assert corps[0]["client_nom"] == "Fatou Diop"
    assert corps[0]["nb_commandes"] == 2  # C1 et C4 (C3 annulée exclue)
    assert corps[0]["chiffre_affaires"] == 115000
    assert corps[0]["solde_du"] == 75000
    assert corps[1]["client_nom"] == "Moussa Ba"
    assert corps[1]["solde_du"] == 12000

    un_seul = client.get(URL + "/top-clients?limite=1", headers=entete_admin).json()
    assert len(un_seul) == 1
    assert client.get(URL + "/top-clients?limite=0", headers=entete_admin).status_code == 422


def test_impayes_les_plus_urgents_d_abord(db, client):
    entete_admin, _, _ = preparer_donnees(db, client)
    corps = client.get(URL + "/impayes", headers=entete_admin).json()
    assert corps["total"] == 3
    soldes = []
    for commande in corps["items"]:
        soldes.append(commande["solde"])
    # C2 (prévue hier), C1 (prévue aujourd'hui), C4 (prévue dans 10 jours)
    assert soldes == [12000, 50000, 25000]
    assert corps["items"][0]["en_retard"] is True

    page = client.get(URL + "/impayes?limit=1&offset=1", headers=entete_admin).json()
    assert page["total"] == 3
    assert len(page["items"]) == 1
    assert page["items"][0]["solde"] == 50000


def test_impayes_exclut_les_commandes_soldees(db, client):
    entete_admin, entete_accueil, _ = preparer_donnees(db, client)
    # Solde complet de C2
    commandes = db.scalars(select(Commande).order_by(Commande.id)).all()
    c2 = commandes[1]
    client.post(
        "/api/v1/commandes/" + str(c2.id) + "/paiements",
        json={"montant": 12000, "mode": "especes"},
        headers=entete_accueil,
    )
    assert client.get(URL + "/impayes", headers=entete_admin).json()["total"] == 2


def test_toutes_les_statistiques_sont_reservees_a_l_admin(db, client):
    adresses = [
        "/tableau-de-bord", "/chiffre-affaires", "/types-vetement", "/top-clients", "/impayes",
    ]
    for role in ["accueil", "tailleur"]:
        entete = entete_pour_role(db, client, role)
        for adresse in adresses:
            assert client.get(URL + adresse, headers=entete).status_code == 403, adresse
    for adresse in adresses:
        assert client.get(URL + adresse).status_code == 401
