from sqlalchemy import select

from app.models import Commande, Utilisateur
from tests.utils import (
    creer_client_bd,
    creer_commande_api,
    creer_prestation_bd,
    entete_pour_role,
)

URL = "/api/v1/commandes"


def preparer_commande(db, client):
    entete_accueil = entete_pour_role(db, client, "accueil")
    fatou = creer_client_bd(db)
    boubou = creer_prestation_bd(db, "Boubou", 35000, 10)
    commande = creer_commande_api(
        client, entete_accueil, fatou.id, [{"type_vetement_id": boubou.id, "quantite": 1}]
    ).json()
    return entete_accueil, commande


def poser_statut(client, entete, commande_id, statut, commentaire=None):
    donnees = {"statut": statut}
    if commentaire is not None:
        donnees["commentaire"] = commentaire
    return client.post(URL + "/" + str(commande_id) + "/statut", json=donnees, headers=entete)


def forcer_statut(db, commande_id, statut):
    commande = db.get(Commande, commande_id)
    commande.statut = statut
    db.commit()


def test_rg15_la_creation_inscrit_la_premiere_ligne(db, client):
    entete, commande = preparer_commande(db, client)
    historique = client.get(URL + "/" + str(commande["id"]) + "/historique", headers=entete).json()
    assert len(historique) == 1
    assert historique[0]["ancien_statut"] is None
    assert historique[0]["nouveau_statut"] == "en_attente"


def test_parcours_complet_avec_aller_retour_essayage_retouches(db, client):
    entete_accueil, commande = preparer_commande(db, client)
    entete_tailleur = entete_pour_role(db, client, "tailleur")
    parcours = [
        "en_coupe", "en_couture", "essayage", "retouches", "essayage", "terminee",
    ]
    for statut in parcours:
        reponse = poser_statut(client, entete_tailleur, commande["id"], statut)
        assert reponse.status_code == 200
        assert reponse.json()["statut"] == statut

    # RG15 : l'historique contient toutes les étapes, dans l'ordre
    historique = client.get(
        URL + "/" + str(commande["id"]) + "/historique", headers=entete_accueil
    ).json()
    suite = []
    for ligne in historique:
        suite.append(ligne["nouveau_statut"])
    assert suite == ["en_attente"] + parcours
    assert historique[1]["ancien_statut"] == "en_attente"
    assert historique[3]["ancien_statut"] == "en_couture"


def test_transition_interdite_409_avec_les_statuts_possibles(db, client):
    entete, commande = preparer_commande(db, client)
    reponse = poser_statut(client, entete, commande["id"], "terminee")
    assert reponse.status_code == 409
    assert reponse.json()["detail"] == (
        "Transition interdite : en_attente → terminee. Statuts possibles : annulee, en_coupe"
    )
    # Le statut n'a pas changé
    assert client.get(URL + "/" + str(commande["id"]), headers=entete).json()["statut"] == "en_attente"


def test_chaque_transition_interdite_du_tableau(db, client):
    entete, commande = preparer_commande(db, client)
    autorisees = {
        "en_attente": ["en_coupe", "annulee"],
        "en_coupe": ["en_couture", "annulee"],
        "en_couture": ["essayage", "terminee", "annulee"],
        "essayage": ["retouches", "terminee", "annulee"],
        "retouches": ["essayage", "terminee", "annulee"],
    }
    tous = [
        "en_attente", "en_coupe", "en_couture", "essayage", "retouches", "terminee", "annulee",
    ]
    for depart, possibles in autorisees.items():
        for cible in tous:
            if cible == depart or cible in possibles:
                continue
            forcer_statut(db, commande["id"], depart)
            reponse = poser_statut(client, entete, commande["id"], cible)
            assert reponse.status_code == 409, depart + " -> " + cible


def test_rg13_meme_statut_409(db, client):
    entete, commande = preparer_commande(db, client)
    assert poser_statut(client, entete, commande["id"], "en_attente").status_code == 409


def test_rg13_livree_ne_se_pose_pas_par_cette_route(db, client):
    entete, commande = preparer_commande(db, client)
    forcer_statut(db, commande["id"], "terminee")
    reponse = poser_statut(client, entete, commande["id"], "livree")
    assert reponse.status_code == 409
    assert "livraison" in reponse.json()["detail"]


def test_statuts_finaux_sans_sortie(db, client):
    entete, commande = preparer_commande(db, client)
    for final in ["livree", "annulee"]:
        forcer_statut(db, commande["id"], final)
        reponse = poser_statut(client, entete, commande["id"], "en_coupe")
        assert reponse.status_code == 409
        assert "aucun" in reponse.json()["detail"]


def test_depuis_terminee_seule_la_livraison_est_possible(db, client):
    entete, commande = preparer_commande(db, client)
    forcer_statut(db, commande["id"], "terminee")
    for cible in ["en_coupe", "annulee", "essayage"]:
        assert poser_statut(client, entete, commande["id"], cible).status_code == 409


def test_statut_inconnu_422_commande_inconnue_404_sans_jeton_401(db, client):
    entete, commande = preparer_commande(db, client)
    assert poser_statut(client, entete, commande["id"], "inconnu").status_code == 422
    assert poser_statut(client, entete, 99999, "en_coupe").status_code == 404
    reponse = client.post(URL + "/" + str(commande["id"]) + "/statut", json={"statut": "en_coupe"})
    assert reponse.status_code == 401


def test_rg14_le_tailleur_ne_peut_pas_annuler_403(db, client):
    entete_accueil, commande = preparer_commande(db, client)
    entete_tailleur = entete_pour_role(db, client, "tailleur")
    assert poser_statut(client, entete_tailleur, commande["id"], "annulee").status_code == 403
    assert client.get(URL + "/" + str(commande["id"]), headers=entete_accueil).json()["statut"] == "en_attente"


def test_l_accueil_et_l_admin_peuvent_annuler(db, client):
    entete_accueil, commande = preparer_commande(db, client)
    assert poser_statut(client, entete_accueil, commande["id"], "annulee").status_code == 200

    entete_admin = entete_pour_role(db, client, "admin")
    forcer_statut(db, commande["id"], "en_attente")
    assert poser_statut(client, entete_admin, commande["id"], "annulee").status_code == 200


def test_rg14_annulation_avec_acompte_exige_un_commentaire(db, client):
    entete, commande = preparer_commande(db, client)
    objet = db.get(Commande, commande["id"])
    objet.montant_paye = 10000
    db.commit()

    assert poser_statut(client, entete, commande["id"], "annulee").status_code == 422
    assert poser_statut(client, entete, commande["id"], "annulee", "   ").status_code == 422
    reponse = poser_statut(client, entete, commande["id"], "annulee", "Acompte remboursé en espèces")
    assert reponse.status_code == 200
    assert reponse.json()["statut"] == "annulee"

    historique = client.get(URL + "/" + str(commande["id"]) + "/historique", headers=entete).json()
    assert historique[-1]["commentaire"] == "Acompte remboursé en espèces"


def test_historique_garde_l_utilisateur_et_le_commentaire(db, client):
    entete_accueil, commande = preparer_commande(db, client)
    entete_tailleur = entete_pour_role(db, client, "tailleur")
    tailleur = db.scalars(select(Utilisateur).where(Utilisateur.role == "tailleur")).first()
    poser_statut(client, entete_tailleur, commande["id"], "en_coupe", "Tissu coupé")
    historique = client.get(
        URL + "/" + str(commande["id"]) + "/historique", headers=entete_accueil
    ).json()
    derniere = historique[-1]
    assert derniere["commentaire"] == "Tissu coupé"
    assert derniere["utilisateur_id"] == tailleur.id
    assert derniere["date_changement"] is not None


def test_historique_404_et_401(db, client):
    entete, commande = preparer_commande(db, client)
    assert client.get(URL + "/99999/historique", headers=entete).status_code == 404
    assert client.get(URL + "/" + str(commande["id"]) + "/historique").status_code == 401
