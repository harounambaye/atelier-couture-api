from datetime import date, timedelta

from sqlalchemy import select

from app.models import Commande, Paiement, Utilisateur
from tests.utils import (
    creer_client_bd,
    creer_commande_api,
    creer_mesure_bd,
    creer_prestation_bd,
    entete_pour_role,
)

URL = "/api/v1/commandes"


def preparer_commande(db, client, remise=0):
    """Une commande de 2 boubous (70 000) + 1 pantalon (12 000), statut en_attente."""
    entete = entete_pour_role(db, client, "accueil")
    fatou = creer_client_bd(db)
    boubou = creer_prestation_bd(db, "Boubou", 35000, 10)
    pantalon = creer_prestation_bd(db, "Pantalon", 12000, 4)
    lignes = [
        {"type_vetement_id": boubou.id, "quantite": 2},
        {"type_vetement_id": pantalon.id, "quantite": 1},
    ]
    commande = creer_commande_api(client, entete, fatou.id, lignes, remise=remise).json()
    return entete, fatou, boubou, pantalon, commande


def changer_statut_en_base(db, commande_id, statut):
    commande = db.get(Commande, commande_id)
    commande.statut = statut
    db.commit()


def enregistrer_paiement_en_base(db, commande_id, montant):
    commande = db.get(Commande, commande_id)
    utilisateur = db.scalars(select(Utilisateur)).first()
    paiement = Paiement(
        commande_id=commande_id,
        montant=montant,
        mode="especes",
        date_paiement=date.today(),
        enregistre_par_id=utilisateur.id,
    )
    db.add(paiement)
    commande.montant_paye = commande.montant_paye + montant
    db.commit()


# ---------- PATCH /commandes/{id} ----------


def test_modification_recalcule_les_montants(db, client):
    entete, fatou, boubou, pantalon, commande = preparer_commande(db, client)
    assert commande["montant_total"] == 82000
    reponse = client.patch(
        URL + "/" + str(commande["id"]),
        json={"remise": 2000, "notes": "Tissu fourni par la cliente"},
        headers=entete,
    )
    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["remise"] == 2000
    assert corps["montant_total"] == 80000
    assert corps["solde"] == 80000
    assert corps["notes"] == "Tissu fourni par la cliente"


def test_modification_date_prevue_et_mesure(db, client):
    entete, fatou, boubou, pantalon, commande = preparer_commande(db, client)
    tailleur = entete_pour_role(db, client, "tailleur")
    tailleur_bd = db.scalars(select(Utilisateur).where(Utilisateur.role == "tailleur")).first()
    mesure = creer_mesure_bd(db, fatou, tailleur_bd.id)
    nouvelle_date = (date.today() + timedelta(days=20)).isoformat()
    reponse = client.patch(
        URL + "/" + str(commande["id"]),
        json={"mesure_id": mesure.id, "date_livraison_prevue": nouvelle_date},
        headers=entete,
    )
    assert reponse.status_code == 200
    assert reponse.json()["mesure_id"] == mesure.id
    assert reponse.json()["date_livraison_prevue"] == nouvelle_date


def test_modification_validations(db, client):
    entete, fatou, boubou, pantalon, commande = preparer_commande(db, client)
    adresse = URL + "/" + str(commande["id"])
    # RG7 : remise > somme des prestations
    assert client.patch(adresse, json={"remise": 82001}, headers=entete).status_code == 422
    # RG8 : date prévue avant la date de commande
    hier = (date.today() - timedelta(days=1)).isoformat()
    assert client.patch(adresse, json={"date_livraison_prevue": hier}, headers=entete).status_code == 422
    # RG9 : mesure d'un autre client
    assert client.patch(adresse, json={"mesure_id": 99999}, headers=entete).status_code == 422
    # champs non vidables
    assert client.patch(adresse, json={"remise": None}, headers=entete).status_code == 422
    assert client.patch(adresse, json={"date_livraison_prevue": None}, headers=entete).status_code == 422
    assert client.patch(URL + "/99999", json={"notes": "x"}, headers=entete).status_code == 404


def test_modification_reservee_a_l_accueil(db, client):
    entete, fatou, boubou, pantalon, commande = preparer_commande(db, client)
    entete_tailleur = entete_pour_role(db, client, "tailleur")
    adresse = URL + "/" + str(commande["id"])
    assert client.patch(adresse, json={"notes": "x"}, headers=entete_tailleur).status_code == 403
    assert client.patch(adresse, json={"notes": "x"}).status_code == 401


def test_rg7_le_total_ne_peut_pas_passer_sous_le_montant_paye(db, client):
    entete, fatou, boubou, pantalon, commande = preparer_commande(db, client)
    enregistrer_paiement_en_base(db, commande["id"], 80000)
    adresse = URL + "/" + str(commande["id"])
    # total passerait à 82 000 - 5 000 = 77 000 < 80 000 déjà payés
    assert client.patch(adresse, json={"remise": 5000}, headers=entete).status_code == 409
    # remise de 2 000 : total 80 000 = montant payé, accepté
    assert client.patch(adresse, json={"remise": 2000}, headers=entete).status_code == 200


def test_rg12_commande_livree_ou_annulee_non_modifiable(db, client):
    entete, fatou, boubou, pantalon, commande = preparer_commande(db, client)
    adresse = URL + "/" + str(commande["id"])
    for statut in ["livree", "annulee"]:
        changer_statut_en_base(db, commande["id"], statut)
        assert client.patch(adresse, json={"notes": "x"}, headers=entete).status_code == 409
        ligne = {"type_vetement_id": boubou.id, "quantite": 1}
        assert client.post(adresse + "/lignes", json=ligne, headers=entete).status_code == 409
        ligne_id = commande["lignes"][0]["id"]
        reponse = client.delete(adresse + "/lignes/" + str(ligne_id), headers=entete)
        assert reponse.status_code == 409


# ---------- Lignes ----------


def test_ajout_d_une_ligne_recalcule(db, client):
    entete, fatou, boubou, pantalon, commande = preparer_commande(db, client)
    adresse = URL + "/" + str(commande["id"]) + "/lignes"
    reponse = client.post(
        adresse,
        json={"type_vetement_id": pantalon.id, "quantite": 2, "prix_unitaire": 10000},
        headers=entete,
    )
    assert reponse.status_code == 201
    corps = reponse.json()
    assert len(corps["lignes"]) == 3
    assert corps["montant_total"] == 82000 + 20000
    assert corps["lignes"][2]["sous_total"] == 20000


def test_ajout_d_une_ligne_prix_par_defaut_et_validations(db, client):
    entete, fatou, boubou, pantalon, commande = preparer_commande(db, client)
    adresse = URL + "/" + str(commande["id"]) + "/lignes"
    corps = client.post(
        adresse, json={"type_vetement_id": pantalon.id, "quantite": 1}, headers=entete
    ).json()
    assert corps["lignes"][2]["prix_unitaire"] == 12000

    assert client.post(
        adresse, json={"type_vetement_id": 99999, "quantite": 1}, headers=entete
    ).status_code == 404
    assert client.post(
        adresse, json={"type_vetement_id": pantalon.id, "quantite": 0}, headers=entete
    ).status_code == 422
    inactive = creer_prestation_bd(db, "Ancienne", 5000, 3, actif=False)
    assert client.post(
        adresse, json={"type_vetement_id": inactive.id, "quantite": 1}, headers=entete
    ).status_code == 422
    assert client.post(
        URL + "/99999/lignes", json={"type_vetement_id": pantalon.id, "quantite": 1}, headers=entete
    ).status_code == 404


def test_rg10_lignes_modifiables_seulement_en_attente(db, client):
    entete, fatou, boubou, pantalon, commande = preparer_commande(db, client)
    changer_statut_en_base(db, commande["id"], "en_coupe")
    adresse = URL + "/" + str(commande["id"])
    ligne = {"type_vetement_id": pantalon.id, "quantite": 1}
    assert client.post(adresse + "/lignes", json=ligne, headers=entete).status_code == 409
    ligne_id = commande["lignes"][0]["id"]
    assert client.delete(adresse + "/lignes/" + str(ligne_id), headers=entete).status_code == 409


def test_retrait_d_une_ligne_recalcule(db, client):
    entete, fatou, boubou, pantalon, commande = preparer_commande(db, client)
    adresse = URL + "/" + str(commande["id"])
    ligne_pantalon = commande["lignes"][1]["id"]
    reponse = client.delete(adresse + "/lignes/" + str(ligne_pantalon), headers=entete)
    assert reponse.status_code == 200
    corps = reponse.json()
    assert len(corps["lignes"]) == 1
    assert corps["montant_total"] == 70000


def test_rg10_une_commande_garde_au_moins_une_ligne(db, client):
    entete, fatou, boubou, pantalon, commande = preparer_commande(db, client)
    adresse = URL + "/" + str(commande["id"])
    client.delete(adresse + "/lignes/" + str(commande["lignes"][1]["id"]), headers=entete)
    derniere = commande["lignes"][0]["id"]
    assert client.delete(adresse + "/lignes/" + str(derniere), headers=entete).status_code == 409


def test_retrait_ligne_inconnue_404(db, client):
    entete, fatou, boubou, pantalon, commande = preparer_commande(db, client)
    adresse = URL + "/" + str(commande["id"])
    assert client.delete(adresse + "/lignes/99999", headers=entete).status_code == 404
    assert client.delete(URL + "/99999/lignes/1", headers=entete).status_code == 404


def test_retrait_ligne_d_une_autre_commande_404(db, client):
    entete, fatou, boubou, pantalon, commande = preparer_commande(db, client)
    autre = creer_commande_api(
        client, entete, fatou.id, [{"type_vetement_id": boubou.id, "quantite": 1}]
    ).json()
    adresse = URL + "/" + str(commande["id"])
    reponse = client.delete(adresse + "/lignes/" + str(autre["lignes"][0]["id"]), headers=entete)
    assert reponse.status_code == 404


def test_retrait_ligne_refuse_si_remise_depasserait_la_somme(db, client):
    entete, fatou, boubou, pantalon, commande = preparer_commande(db, client, remise=20000)
    adresse = URL + "/" + str(commande["id"])
    # Sans le boubou x2 il ne reste que 12 000 de prestations pour 20 000 de remise
    reponse = client.delete(adresse + "/lignes/" + str(commande["lignes"][0]["id"]), headers=entete)
    assert reponse.status_code == 422


def test_rg7_retrait_ligne_refuse_si_total_sous_le_montant_paye(db, client):
    entete, fatou, boubou, pantalon, commande = preparer_commande(db, client)
    enregistrer_paiement_en_base(db, commande["id"], 50000)
    adresse = URL + "/" + str(commande["id"])
    # Retirer le boubou x2 ramènerait le total à 12 000 < 50 000 payés
    reponse = client.delete(adresse + "/lignes/" + str(commande["lignes"][0]["id"]), headers=entete)
    assert reponse.status_code == 409


def test_lignes_reservees_a_l_accueil(db, client):
    entete, fatou, boubou, pantalon, commande = preparer_commande(db, client)
    entete_tailleur = entete_pour_role(db, client, "tailleur")
    adresse = URL + "/" + str(commande["id"])
    ligne = {"type_vetement_id": pantalon.id, "quantite": 1}
    assert client.post(adresse + "/lignes", json=ligne, headers=entete_tailleur).status_code == 403
    ligne_id = commande["lignes"][0]["id"]
    reponse = client.delete(adresse + "/lignes/" + str(ligne_id), headers=entete_tailleur)
    assert reponse.status_code == 403
