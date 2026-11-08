from datetime import date, timedelta

from app.models import Commande
from tests.utils import (
    creer_client_bd,
    creer_commande_api,
    creer_prestation_bd,
    entete_pour_role,
)

URL = "/api/v1/commandes"


def preparer_commande(db, client, telephone="771234567", nom="Diop", entete=None):
    """Commande de 35 000 FCFA. Renvoie (entête accueil, commande)."""
    if entete is None:
        entete = entete_pour_role(db, client, "accueil")
    fatou = creer_client_bd(db, telephone=telephone, nom=nom)
    boubou = creer_prestation_bd(db, "Boubou" + telephone, 35000, 10)
    commande = creer_commande_api(
        client, entete, fatou.id, [{"type_vetement_id": boubou.id, "quantite": 1}]
    ).json()
    return entete, commande


def forcer_statut(db, commande_id, statut):
    commande = db.get(Commande, commande_id)
    commande.statut = statut
    db.commit()


def planifier(client, entete, commande_id, mode="retrait_atelier", jours=5, **extras):
    donnees = {"mode": mode, "date_prevue": (date.today() + timedelta(days=jours)).isoformat()}
    donnees.update(extras)
    return client.put(URL + "/" + str(commande_id) + "/livraison", json=donnees, headers=entete)


def confirmer(client, entete, commande_id, corps=None):
    adresse = URL + "/" + str(commande_id) + "/livraison/confirmer"
    if corps is None:
        return client.post(adresse, headers=entete)
    return client.post(adresse, json=corps, headers=entete)


def payer(client, entete, commande_id, montant):
    donnees = {"montant": montant, "mode": "especes"}
    return client.post(URL + "/" + str(commande_id) + "/paiements", json=donnees, headers=entete)


# ---------- Planification ----------


def test_planification_met_a_jour_la_date_de_la_commande(db, client):
    entete, commande = preparer_commande(db, client)
    reponse = planifier(client, entete, commande["id"], "retrait_atelier", jours=3, livreur="Moussa")
    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["statut"] == "planifiee"
    assert corps["mode"] == "retrait_atelier"
    assert corps["livreur"] == "Moussa"
    assert corps["date_effective"] is None

    nouvelle_date = (date.today() + timedelta(days=3)).isoformat()
    commande_mise_a_jour = client.get(URL + "/" + str(commande["id"]), headers=entete).json()
    assert commande_mise_a_jour["date_livraison_prevue"] == nouvelle_date
    assert commande_mise_a_jour["livraison"]["date_prevue"] == nouvelle_date


def test_rg18_domicile_exige_une_adresse(db, client):
    entete, commande = preparer_commande(db, client)
    assert planifier(client, entete, commande["id"], "domicile").status_code == 422
    assert planifier(client, entete, commande["id"], "domicile", adresse="   ").status_code == 422
    reponse = planifier(client, entete, commande["id"], "domicile", adresse="Dakar, Médina")
    assert reponse.status_code == 200
    assert reponse.json()["adresse"] == "Dakar, Médina"


def test_rg18_replanifier_modifie_la_livraison_existante(db, client):
    entete, commande = preparer_commande(db, client)
    premiere = planifier(client, entete, commande["id"], "retrait_atelier", jours=3).json()
    seconde = planifier(client, entete, commande["id"], "domicile", jours=8, adresse="Thiès").json()
    assert seconde["id"] == premiere["id"]
    assert seconde["mode"] == "domicile"
    liste = client.get("/api/v1/livraisons", headers=entete).json()
    assert len(liste) == 1
    nouvelle_date = (date.today() + timedelta(days=8)).isoformat()
    assert client.get(URL + "/" + str(commande["id"]), headers=entete).json()["date_livraison_prevue"] == nouvelle_date


def test_planification_validations(db, client):
    entete, commande = preparer_commande(db, client)
    # Date avant la date de commande
    assert planifier(client, entete, commande["id"], jours=-2).status_code == 422
    # Mode inconnu
    assert planifier(client, entete, commande["id"], mode="drone").status_code == 422
    # Commande inconnue
    assert planifier(client, entete, 99999).status_code == 404


def test_planification_409_si_commande_livree_ou_annulee(db, client):
    entete, commande = preparer_commande(db, client)
    for statut in ["livree", "annulee"]:
        forcer_statut(db, commande["id"], statut)
        assert planifier(client, entete, commande["id"]).status_code == 409


def test_planification_et_confirmation_reservees_a_l_accueil(db, client):
    entete, commande = preparer_commande(db, client)
    entete_tailleur = entete_pour_role(db, client, "tailleur")
    assert planifier(client, entete_tailleur, commande["id"]).status_code == 403
    assert confirmer(client, entete_tailleur, commande["id"]).status_code == 403
    assert client.put(URL + "/" + str(commande["id"]) + "/livraison", json={}).status_code == 401
    entete_admin = entete_pour_role(db, client, "admin")
    assert planifier(client, entete_admin, commande["id"]).status_code == 200


# ---------- Lecture ----------


def test_lecture_de_la_livraison_et_404(db, client):
    entete, commande = preparer_commande(db, client)
    adresse = URL + "/" + str(commande["id"]) + "/livraison"
    assert client.get(adresse, headers=entete).status_code == 404
    planifier(client, entete, commande["id"])
    entete_tailleur = entete_pour_role(db, client, "tailleur")
    assert client.get(adresse, headers=entete_tailleur).status_code == 200
    assert client.get(URL + "/99999/livraison", headers=entete).status_code == 404


# ---------- Confirmation ----------


def test_rg19_confirmation_exige_une_commande_terminee_409(db, client):
    entete, commande = preparer_commande(db, client)
    for statut in ["en_attente", "en_couture", "annulee", "livree"]:
        forcer_statut(db, commande["id"], statut)
        assert confirmer(client, entete, commande["id"]).status_code == 409
    assert confirmer(client, entete, 99999).status_code == 404


def test_rg19_commande_non_soldee_409_avec_le_montant(db, client):
    entete, commande = preparer_commande(db, client)
    forcer_statut(db, commande["id"], "terminee")
    payer(client, entete, commande["id"], 10000)
    reponse = confirmer(client, entete, commande["id"])
    assert reponse.status_code == 409
    assert "25000" in reponse.json()["detail"]
    assert client.get(URL + "/" + str(commande["id"]), headers=entete).json()["statut"] == "terminee"


def test_rg20_confirmation_d_une_commande_soldee(db, client):
    entete, commande = preparer_commande(db, client)
    planifier(client, entete, commande["id"], "domicile", adresse="Dakar", jours=2)
    forcer_statut(db, commande["id"], "terminee")
    payer(client, entete, commande["id"], 35000)

    reponse = confirmer(client, entete, commande["id"])
    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["statut"] == "livree"
    assert corps["solde"] == 0
    assert corps["date_livraison_reelle"] == date.today().isoformat()
    assert corps["livraison"]["statut"] == "livree"
    assert corps["livraison"]["date_effective"] == date.today().isoformat()
    assert corps["livraison"]["mode"] == "domicile"
    assert corps["en_retard"] is False

    historique = client.get(URL + "/" + str(commande["id"]) + "/historique", headers=entete).json()
    assert historique[-1]["ancien_statut"] == "terminee"
    assert historique[-1]["nouveau_statut"] == "livree"


def test_rg20_sans_planification_un_retrait_atelier_est_cree(db, client):
    entete, commande = preparer_commande(db, client)
    forcer_statut(db, commande["id"], "terminee")
    payer(client, entete, commande["id"], 35000)
    corps = confirmer(client, entete, commande["id"]).json()
    assert corps["livraison"] is not None
    assert corps["livraison"]["mode"] == "retrait_atelier"
    assert corps["livraison"]["statut"] == "livree"
    assert corps["livraison"]["commande_id"] == commande["id"]


def test_rg19_solde_impaye_autorise_avec_mention_dans_l_historique(db, client):
    entete, commande = preparer_commande(db, client)
    forcer_statut(db, commande["id"], "terminee")
    payer(client, entete, commande["id"], 10000)
    reponse = confirmer(client, entete, commande["id"], {"autoriser_solde_impaye": True})
    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["statut"] == "livree"
    assert corps["solde"] == 25000  # la dette reste visible
    historique = client.get(URL + "/" + str(commande["id"]) + "/historique", headers=entete).json()
    assert "25000" in historique[-1]["commentaire"]
    assert "impayé" in historique[-1]["commentaire"]


def test_confirmation_avec_date_effective(db, client):
    entete, commande = preparer_commande(db, client)
    forcer_statut(db, commande["id"], "terminee")
    payer(client, entete, commande["id"], 35000)
    hier = (date.today() - timedelta(days=1)).isoformat()
    corps = confirmer(client, entete, commande["id"], {"date_effective": hier}).json()
    assert corps["date_livraison_reelle"] == hier
    assert corps["livraison"]["date_effective"] == hier


def test_confirmation_date_future_422(db, client):
    entete, commande = preparer_commande(db, client)
    forcer_statut(db, commande["id"], "terminee")
    payer(client, entete, commande["id"], 35000)
    demain = (date.today() + timedelta(days=1)).isoformat()
    assert confirmer(client, entete, commande["id"], {"date_effective": demain}).status_code == 422


def test_une_commande_livree_ne_se_confirme_pas_deux_fois(db, client):
    entete, commande = preparer_commande(db, client)
    forcer_statut(db, commande["id"], "terminee")
    payer(client, entete, commande["id"], 35000)
    assert confirmer(client, entete, commande["id"]).status_code == 200
    assert confirmer(client, entete, commande["id"]).status_code == 409


# ---------- Tournée ----------


def test_tournee_triee_avec_champs_de_la_commande(db, client):
    entete, c1 = preparer_commande(db, client, telephone="771111111", nom="Diop")
    _, c2 = preparer_commande(db, client, "772222222", "Ba", entete)
    _, c3 = preparer_commande(db, client, "773333333", "Sow", entete)
    planifier(client, entete, c1["id"], jours=9)
    planifier(client, entete, c2["id"], jours=2)
    planifier(client, entete, c3["id"], jours=5)
    payer(client, entete, c2["id"], 5000)

    entete_tailleur = entete_pour_role(db, client, "tailleur")
    liste = client.get("/api/v1/livraisons", headers=entete_tailleur).json()
    numeros = []
    for element in liste:
        numeros.append(element["numero_commande"])
    assert numeros == [c2["numero"], c3["numero"], c1["numero"]]
    premier = liste[0]
    assert premier["client_nom"] == "Fatou Ba"
    assert premier["client_telephone"] == "772222222"
    assert premier["solde_commande"] == 30000
    assert premier["statut"] == "planifiee"
    assert client.get("/api/v1/livraisons").status_code == 401


def test_tournee_filtres(db, client):
    entete, c1 = preparer_commande(db, client, telephone="771111111")
    _, c2 = preparer_commande(db, client, "772222222", "Ba", entete)
    planifier(client, entete, c1["id"], jours=2)
    planifier(client, entete, c2["id"], jours=10)
    forcer_statut(db, c1["id"], "terminee")
    payer(client, entete, c1["id"], 35000)
    confirmer(client, entete, c1["id"])

    assert len(client.get("/api/v1/livraisons?statut=livree", headers=entete).json()) == 1
    assert len(client.get("/api/v1/livraisons?statut=planifiee", headers=entete).json()) == 1
    assert client.get("/api/v1/livraisons?statut=autre", headers=entete).status_code == 422

    apres = (date.today() + timedelta(days=5)).isoformat()
    liste = client.get("/api/v1/livraisons?date_min=" + apres, headers=entete).json()
    assert len(liste) == 1
    assert liste[0]["numero_commande"] == c2["numero"]
    liste = client.get("/api/v1/livraisons?date_max=" + apres, headers=entete).json()
    assert len(liste) == 1
    assert liste[0]["numero_commande"] == c1["numero"]
