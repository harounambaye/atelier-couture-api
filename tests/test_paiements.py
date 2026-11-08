from datetime import date, timedelta

from app.models import Commande
from tests.utils import (
    creer_client_bd,
    creer_commande_api,
    creer_prestation_bd,
    entete_pour_role,
)

URL = "/api/v1/commandes"


def preparer_commande(db, client):
    """Commande de 35 000 FCFA (un boubou)."""
    entete = entete_pour_role(db, client, "accueil")
    fatou = creer_client_bd(db)
    boubou = creer_prestation_bd(db, "Boubou", 35000, 10)
    commande = creer_commande_api(
        client, entete, fatou.id, [{"type_vetement_id": boubou.id, "quantite": 1}]
    ).json()
    return entete, commande


def payer(client, entete, commande_id, montant, mode="wave", **extras):
    donnees = {"montant": montant, "mode": mode}
    donnees.update(extras)
    return client.post(URL + "/" + str(commande_id) + "/paiements", json=donnees, headers=entete)


def lire_commande_api(client, entete, commande_id):
    return client.get(URL + "/" + str(commande_id), headers=entete).json()


def test_encaissement_201_met_a_jour_payé_et_solde(db, client):
    entete, commande = preparer_commande(db, client)
    reponse = payer(client, entete, commande["id"], 10000, "wave", reference="WAVE-123")
    assert reponse.status_code == 201
    corps = reponse.json()
    assert corps["montant"] == 10000
    assert corps["mode"] == "wave"
    assert corps["reference"] == "WAVE-123"
    assert corps["date_paiement"] == date.today().isoformat()
    assert corps["commande_id"] == commande["id"]

    mise_a_jour = lire_commande_api(client, entete, commande["id"])
    assert mise_a_jour["montant_paye"] == 10000
    assert mise_a_jour["solde"] == 25000
    assert len(mise_a_jour["paiements"]) == 1


def test_plusieurs_paiements_jusqu_a_solder(db, client):
    entete, commande = preparer_commande(db, client)
    assert payer(client, entete, commande["id"], 10000).status_code == 201
    assert payer(client, entete, commande["id"], 25000, "especes").status_code == 201
    assert lire_commande_api(client, entete, commande["id"])["solde"] == 0


def test_rg16_paiement_superieur_au_solde_409(db, client):
    entete, commande = preparer_commande(db, client)
    payer(client, entete, commande["id"], 10000)
    assert payer(client, entete, commande["id"], 25001).status_code == 409
    # Rien n'a été enregistré
    assert lire_commande_api(client, entete, commande["id"])["montant_paye"] == 10000


def test_rg16_montant_invalide_422(db, client):
    entete, commande = preparer_commande(db, client)
    assert payer(client, entete, commande["id"], 0).status_code == 422
    assert payer(client, entete, commande["id"], -500).status_code == 422
    assert payer(client, entete, commande["id"], 1000, mode="bitcoin").status_code == 422


def test_rg16_date_future_422_et_date_passee_acceptee(db, client):
    entete, commande = preparer_commande(db, client)
    demain = (date.today() + timedelta(days=1)).isoformat()
    assert payer(client, entete, commande["id"], 1000, date_paiement=demain).status_code == 422
    hier = (date.today() - timedelta(days=1)).isoformat()
    reponse = payer(client, entete, commande["id"], 1000, date_paiement=hier)
    assert reponse.status_code == 201
    assert reponse.json()["date_paiement"] == hier


def test_rg16_commande_annulee_409(db, client):
    entete, commande = preparer_commande(db, client)
    objet = db.get(Commande, commande["id"])
    objet.statut = "annulee"
    db.commit()
    assert payer(client, entete, commande["id"], 1000).status_code == 409


def test_commande_inconnue_404(db, client):
    entete, commande = preparer_commande(db, client)
    assert payer(client, entete, 99999, 1000).status_code == 404
    assert client.get(URL + "/99999/paiements", headers=entete).status_code == 404


def test_encaissement_reserve_a_l_accueil_et_a_l_admin(db, client):
    entete, commande = preparer_commande(db, client)
    entete_tailleur = entete_pour_role(db, client, "tailleur")
    assert payer(client, entete_tailleur, commande["id"], 1000).status_code == 403
    entete_admin = entete_pour_role(db, client, "admin")
    assert payer(client, entete_admin, commande["id"], 1000).status_code == 201
    reponse = client.post(
        URL + "/" + str(commande["id"]) + "/paiements", json={"montant": 1000, "mode": "wave"}
    )
    assert reponse.status_code == 401


def test_liste_des_paiements_dans_l_ordre_de_saisie(db, client):
    entete, commande = preparer_commande(db, client)
    payer(client, entete, commande["id"], 5000, "wave")
    payer(client, entete, commande["id"], 7000, "especes")
    payer(client, entete, commande["id"], 3000, "cheque")
    entete_tailleur = entete_pour_role(db, client, "tailleur")
    reponse = client.get(URL + "/" + str(commande["id"]) + "/paiements", headers=entete_tailleur)
    assert reponse.status_code == 200
    montants = []
    for paiement in reponse.json():
        montants.append(paiement["montant"])
    assert montants == [5000, 7000, 3000]


def test_rg17_annulation_par_l_admin_recalcule(db, client):
    entete, commande = preparer_commande(db, client)
    premier = payer(client, entete, commande["id"], 10000).json()
    payer(client, entete, commande["id"], 5000)
    entete_admin = entete_pour_role(db, client, "admin")

    reponse = client.delete("/api/v1/paiements/" + str(premier["id"]), headers=entete_admin)
    assert reponse.status_code == 204

    mise_a_jour = lire_commande_api(client, entete, commande["id"])
    assert mise_a_jour["montant_paye"] == 5000
    assert mise_a_jour["solde"] == 30000
    assert len(mise_a_jour["paiements"]) == 1


def test_rg17_annulation_reservee_a_l_admin_404_401(db, client):
    entete, commande = preparer_commande(db, client)
    paiement = payer(client, entete, commande["id"], 10000).json()
    adresse = "/api/v1/paiements/" + str(paiement["id"])
    assert client.delete(adresse, headers=entete).status_code == 403
    entete_tailleur = entete_pour_role(db, client, "tailleur")
    assert client.delete(adresse, headers=entete_tailleur).status_code == 403
    assert client.delete(adresse).status_code == 401
    entete_admin = entete_pour_role(db, client, "admin")
    assert client.delete("/api/v1/paiements/99999", headers=entete_admin).status_code == 404
    assert lire_commande_api(client, entete, commande["id"])["montant_paye"] == 10000


def test_apres_annulation_on_peut_encaisser_de_nouveau(db, client):
    entete, commande = preparer_commande(db, client)
    paiement = payer(client, entete, commande["id"], 35000).json()
    assert payer(client, entete, commande["id"], 1000).status_code == 409
    entete_admin = entete_pour_role(db, client, "admin")
    client.delete("/api/v1/paiements/" + str(paiement["id"]), headers=entete_admin)
    assert payer(client, entete, commande["id"], 35000).status_code == 201
