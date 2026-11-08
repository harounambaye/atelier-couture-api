from tests.utils import entete_pour_role

# Chaque entrée : (méthode, chemin, corps JSON ou None, rôles autorisés)
# L'admin est toujours autorisé. Les identifiants (1, 99999...) n'ont pas besoin d'exister :
# un rôle autorisé reçoit 404 ou 422, jamais 401 ni 403.
ADMIN = ["admin"]
ACCUEIL = ["admin", "accueil"]
TAILLEUR = ["admin", "tailleur"]
TOUS = ["admin", "accueil", "tailleur"]

ROUTES = [
    # Comptes
    ("POST", "/utilisateurs", {"email": "a@b.sn"}, ADMIN),
    ("GET", "/utilisateurs", None, ADMIN),
    ("GET", "/utilisateurs/1", None, ADMIN),
    ("PATCH", "/utilisateurs/99999", {"actif": False}, ADMIN),
    # Clients
    ("POST", "/clients", {"nom": "x"}, TOUS),
    ("GET", "/clients", None, TOUS),
    ("GET", "/clients/99999", None, TOUS),
    ("PATCH", "/clients/99999", {"notes": "x"}, TOUS),
    ("DELETE", "/clients/99999", None, ADMIN),
    ("GET", "/clients/99999/commandes", None, TOUS),
    ("GET", "/clients/99999/resume", None, TOUS),
    # Catalogue
    ("POST", "/catalogue", {"nom": "x"}, ADMIN),
    ("GET", "/catalogue", None, TOUS),
    ("GET", "/catalogue/99999", None, TOUS),
    ("PATCH", "/catalogue/99999", {"prix_base": 1}, ADMIN),
    # Mesures
    ("POST", "/clients/99999/mesures", {"tour_cou": 38}, TAILLEUR),
    ("GET", "/clients/99999/mesures", None, TOUS),
    ("GET", "/clients/99999/mesures/derniere", None, TOUS),
    ("GET", "/mesures/99999", None, TOUS),
    ("PATCH", "/mesures/99999", {"tour_cou": 38}, TAILLEUR),
    ("DELETE", "/mesures/99999", None, TAILLEUR),
    # Commandes
    ("POST", "/commandes", {"client_id": 99999, "lignes": []}, ACCUEIL),
    ("GET", "/commandes", None, TOUS),
    ("GET", "/commandes/99999", None, TOUS),
    ("PATCH", "/commandes/99999", {"notes": "x"}, ACCUEIL),
    ("POST", "/commandes/99999/statut", {"statut": "en_coupe"}, TOUS),
    ("GET", "/commandes/99999/historique", None, TOUS),
    ("POST", "/commandes/99999/lignes", {"type_vetement_id": 1, "quantite": 1}, ACCUEIL),
    ("DELETE", "/commandes/99999/lignes/1", None, ACCUEIL),
    # Paiements
    ("POST", "/commandes/99999/paiements", {"montant": 100, "mode": "wave"}, ACCUEIL),
    ("GET", "/commandes/99999/paiements", None, TOUS),
    ("DELETE", "/paiements/99999", None, ADMIN),
    # Livraisons
    ("PUT", "/commandes/99999/livraison", {"mode": "retrait_atelier", "date_prevue": "2030-01-01"}, ACCUEIL),
    ("GET", "/commandes/99999/livraison", None, TOUS),
    ("POST", "/commandes/99999/livraison/confirmer", None, ACCUEIL),
    ("GET", "/livraisons", None, TOUS),
    # Statistiques
    ("GET", "/statistiques/tableau-de-bord", None, ADMIN),
    ("GET", "/statistiques/chiffre-affaires", None, ADMIN),
    ("GET", "/statistiques/types-vetement", None, ADMIN),
    ("GET", "/statistiques/top-clients", None, ADMIN),
    ("GET", "/statistiques/impayes", None, ADMIN),
]


def appeler(client, methode, chemin, corps, entete):
    url = "/api/v1" + chemin
    if corps is None:
        return client.request(methode, url, headers=entete)
    return client.request(methode, url, json=corps, headers=entete)


def test_sans_jeton_toutes_les_routes_protegees_repondent_401(client):
    for methode, chemin, corps, roles in ROUTES:
        reponse = appeler(client, methode, chemin, corps, None)
        assert reponse.status_code == 401, methode + " " + chemin


def test_matrice_des_droits_par_role(db, client):
    entetes = {}
    for role in ["admin", "accueil", "tailleur"]:
        entetes[role] = entete_pour_role(db, client, role)

    for methode, chemin, corps, roles_autorises in ROUTES:
        for role in ["admin", "accueil", "tailleur"]:
            reponse = appeler(client, methode, chemin, corps, entetes[role])
            description = methode + " " + chemin + " avec le rôle " + role
            if role in roles_autorises:
                assert reponse.status_code not in (401, 403), description
            else:
                assert reponse.status_code == 403, description
