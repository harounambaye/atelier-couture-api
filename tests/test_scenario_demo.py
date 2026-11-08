"""Scénario de démonstration (annexe A du cahier des charges), joué de bout en bout."""

from datetime import date, timedelta

from sqlalchemy import select

from app.models import Commande, TypeVetement
from app.seed import creer_catalogue
from tests.utils import entete_pour_role

API = "/api/v1"


def trouver_prestation(db, nom):
    return db.scalars(select(TypeVetement).where(TypeVetement.nom == nom)).first()


def test_scenario_de_demonstration(db, client):
    creer_catalogue(db)
    db.commit()
    boubou = trouver_prestation(db, "Boubou")
    pantalon = trouver_prestation(db, "Pantalon")

    entete_accueil = entete_pour_role(db, client, "accueil")
    entete_tailleur = entete_pour_role(db, client, "tailleur")
    entete_admin = entete_pour_role(db, client, "admin")

    # 1. L'accueil crée « Fatou Diop » ; un second client avec le même numéro -> 409
    reponse = client.post(
        API + "/clients",
        json={"nom": "Diop", "prenom": "Fatou", "telephone": "77 123 45 67", "genre": "femme"},
        headers=entete_accueil,
    )
    assert reponse.status_code == 201
    fatou = reponse.json()
    assert fatou["telephone"] == "771234567"
    doublon = client.post(
        API + "/clients",
        json={"nom": "Autre", "prenom": "Personne", "telephone": "771234567", "genre": "homme"},
        headers=entete_accueil,
    )
    assert doublon.status_code == 409

    # 2. Le tailleur prend les mesures ; l'accueil qui tente la même action -> 403
    adresse_mesures = API + "/clients/" + str(fatou["id"]) + "/mesures"
    mesures = {"tour_poitrine": 92, "tour_taille": 70, "tour_bassin": 98}
    assert client.post(adresse_mesures, json=mesures, headers=entete_accueil).status_code == 403
    reponse = client.post(adresse_mesures, json=mesures, headers=entete_tailleur)
    assert reponse.status_code == 201
    prise = reponse.json()

    # 3. Commande : 2 boubous + 1 pantalon à prix négocié, avec remise
    reponse = client.post(
        API + "/commandes",
        json={
            "client_id": fatou["id"],
            "lignes": [
                {"type_vetement_id": boubou.id, "quantite": 2},
                {"type_vetement_id": pantalon.id, "quantite": 1, "prix_unitaire": 10000},
            ],
            "remise": 5000,
        },
        headers=entete_accueil,
    )
    assert reponse.status_code == 201
    commande = reponse.json()
    assert commande["numero"] == "CMD-" + str(date.today().year) + "-" + str(commande["id"]).zfill(5)
    assert commande["montant_total"] == 2 * 35000 + 10000 - 5000  # 75 000
    assert commande["date_livraison_prevue"] == (date.today() + timedelta(days=10)).isoformat()
    assert commande["mesure_id"] == prise["id"]
    adresse_commande = API + "/commandes/" + str(commande["id"])

    # 4. L'accueil tente « terminee » depuis « en_attente » -> 409 avec les statuts possibles
    reponse = client.post(adresse_commande + "/statut", json={"statut": "terminee"}, headers=entete_accueil)
    assert reponse.status_code == 409
    assert "annulee, en_coupe" in reponse.json()["detail"]

    # 5. Le tailleur avance jusqu'à « terminee » avec un aller-retour essayage / retouches
    for statut in ["en_coupe", "en_couture", "essayage", "retouches", "essayage", "terminee"]:
        reponse = client.post(
            adresse_commande + "/statut", json={"statut": statut}, headers=entete_tailleur
        )
        assert reponse.status_code == 200
    historique = client.get(adresse_commande + "/historique", headers=entete_accueil).json()
    etapes = []
    for ligne in historique:
        etapes.append(ligne["nouveau_statut"])
    assert etapes == [
        "en_attente", "en_coupe", "en_couture", "essayage", "retouches", "essayage", "terminee",
    ]

    # 6. Acompte Wave ; un paiement supérieur au solde -> 409
    reponse = client.post(
        adresse_commande + "/paiements",
        json={"montant": 30000, "mode": "wave", "reference": "WAVE-001"},
        headers=entete_accueil,
    )
    assert reponse.status_code == 201
    trop = client.post(
        adresse_commande + "/paiements",
        json={"montant": 45001, "mode": "especes"},
        headers=entete_accueil,
    )
    assert trop.status_code == 409

    # 7. Confirmer la livraison avec un solde impayé -> 409
    reponse = client.post(adresse_commande + "/livraison/confirmer", headers=entete_accueil)
    assert reponse.status_code == 409
    assert "45000" in reponse.json()["detail"]

    # 8. L'accueil encaisse le solde puis confirme : « livree », solde 0
    reponse = client.post(
        adresse_commande + "/paiements",
        json={"montant": 45000, "mode": "especes"},
        headers=entete_accueil,
    )
    assert reponse.status_code == 201
    reponse = client.post(adresse_commande + "/livraison/confirmer", headers=entete_accueil)
    assert reponse.status_code == 200
    assert reponse.json()["statut"] == "livree"
    assert reponse.json()["solde"] == 0

    # 9. L'admin voit le CA du mois ; l'accueil sur les statistiques -> 403
    tableau = client.get(API + "/statistiques/tableau-de-bord", headers=entete_admin)
    assert tableau.status_code == 200
    assert tableau.json()["chiffre_affaires_mois"] == 75000
    assert tableau.json()["encaisse_mois"] == 75000
    assert tableau.json()["commandes_par_statut"]["livree"] == 1
    assert client.get(API + "/statistiques/tableau-de-bord", headers=entete_accueil).status_code == 403

    # 10. Impayés et commandes en retard : on crée une seconde commande, laissée en retard
    reponse = client.post(
        API + "/commandes",
        json={"client_id": fatou["id"], "lignes": [{"type_vetement_id": pantalon.id, "quantite": 1}]},
        headers=entete_accueil,
    )
    seconde = reponse.json()
    objet = db.get(Commande, seconde["id"])
    objet.date_livraison_prevue = date.today() - timedelta(days=3)
    db.commit()

    impayes = client.get(API + "/statistiques/impayes", headers=entete_admin).json()
    assert impayes["total"] == 1
    assert impayes["items"][0]["numero"] == seconde["numero"]
    assert impayes["items"][0]["solde"] == 12000

    en_retard = client.get(API + "/commandes?en_retard=true", headers=entete_admin).json()
    assert en_retard["total"] == 1
    assert en_retard["items"][0]["numero"] == seconde["numero"]
    assert client.get(API + "/statistiques/tableau-de-bord", headers=entete_admin).json()[
        "nb_commandes_en_retard"
    ] == 1
