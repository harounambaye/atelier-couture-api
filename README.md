# API de gestion d'un atelier de couture

Projet final du module « Développement d'API avec FastAPI et PostgreSQL ».

Back-end REST (FastAPI + PostgreSQL) pour gérer les clients, mesures, commandes,
paiements et livraisons d'un atelier de couture à Dakar.

- **FastAPI** + Swagger sur `/docs`
- **PostgreSQL 17** (dans Docker), **SQLAlchemy 2** (style moderne) et **Alembic** pour les migrations
- **Pydantic 2** : schémas distincts pour la création, la modification et la lecture
- Authentification **JWT**, mots de passe hachés avec **Argon2**
- Tests **pytest** sur une base PostgreSQL dédiée (`atelier_test`)

## Architecture

```
app/
├── main.py            application FastAPI, préfixe /api/v1
├── config.py          configuration lue dans le fichier .env
├── database.py        moteur SQLAlchemy, session, Base
├── security.py        hachage Argon2 et jetons JWT
├── dependencies.py    utilisateur connecté (401) et contrôle des rôles (403)
├── seed.py            premier administrateur + catalogue de départ
├── models/            tables SQLAlchemy (un fichier par entité)
├── schemas/           schémas Pydantic (création / modification / lecture)
├── services/          TOUTE la logique métier (règles de gestion)
└── routers/           un fichier par domaine : droits -> service -> commit
alembic/               migrations (le schéma n'est jamais créé par create_all)
tests/                 tests pytest
docker/                script de démarrage du conteneur et init de la base de test
```

Les routeurs ne contiennent aucune règle de gestion : ils vérifient les droits, appellent un
service, puis font le `commit`. Les services lèvent des `HTTPException` avec des messages en
français. Aucun modèle brut ni aucun hash de mot de passe n'est jamais renvoyé.

## Prérequis

- Python 3.13
- Docker Desktop (PostgreSQL tourne dans Docker)
- Git

## Installation (PowerShell)

```powershell
git clone <url-du-depot>
cd atelier-couture-api

python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Configuration : copier le modèle puis remplacer les valeurs « changez_moi »
Copy-Item .env.example .env
```

Dans le fichier `.env`, renseignez au minimum :

| Variable | Rôle |
|---|---|
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | création de la base par Docker |
| `DATABASE_URL` | connexion de l'API (doit reprendre les valeurs ci-dessus) |
| `TEST_DATABASE_URL` | base de test, **différente** de `DATABASE_URL` (`.../atelier_test`) |
| `SECRET_KEY` | clé de signature des jetons : `python -c "import secrets; print(secrets.token_hex(32))"` |
| `ADMIN_EMAIL`, `ADMIN_TELEPHONE`, `ADMIN_NOM_COMPLET`, `ADMIN_MOT_DE_PASSE` | premier administrateur (mot de passe : 8 caractères minimum) |

Le fichier `.env` n'est jamais commité.

## Lancement en développement (API dans le venv, base dans Docker)

```powershell
docker compose up -d db          # démarre PostgreSQL (attendre « healthy » : docker compose ps)
alembic upgrade head             # crée toutes les tables
python -m app.seed               # crée l'administrateur et le catalogue de départ (idempotent)
uvicorn app.main:app --reload    # API sur http://127.0.0.1:8000
```

- Swagger : <http://127.0.0.1:8000/docs>
- Santé : <http://127.0.0.1:8000/health>

## Lancement complet avec Docker (API + base)

```powershell
docker compose up --build
```

Le conteneur de l'API applique les migrations, exécute le seed (administrateur + catalogue),
puis démarre `uvicorn`. L'API est alors disponible sur <http://127.0.0.1:8000/docs>.
Pour tout arrêter : `docker compose down` (ajoutez `-v` pour effacer aussi les données).

## Comptes de test

Le seul compte créé automatiquement est l'**administrateur**, avec les valeurs `ADMIN_*` du `.env`
(avec le modèle : `admin@atelier.sn`, téléphone `770000000`, mot de passe choisi dans `.env`).

La connexion se fait par **e-mail ou par numéro de téléphone** (champ `username` du formulaire).

Les comptes **accueil** et **tailleur** se créent depuis Swagger (bouton *Authorize* avec le compte
admin, puis `POST /api/v1/utilisateurs`) ou en ligne de commande :

```powershell
# 1. Connexion de l'admin : récupérer le jeton
curl.exe -X POST http://127.0.0.1:8000/api/v1/auth/login -d "username=admin@atelier.sn&password=VOTRE_MOT_DE_PASSE"

# 2. Créer un compte accueil (remplacer <JETON> par la valeur de access_token)
curl.exe -X POST http://127.0.0.1:8000/api/v1/utilisateurs -H "Authorization: Bearer <JETON>" -H "Content-Type: application/json" -d "{\"email\":\"accueil@atelier.sn\",\"telephone\":\"771111111\",\"nom_complet\":\"Awa Accueil\",\"mot_de_passe\":\"MotDePasse123\",\"role\":\"accueil\"}"

# 3. Créer un compte tailleur
curl.exe -X POST http://127.0.0.1:8000/api/v1/utilisateurs -H "Authorization: Bearer <JETON>" -H "Content-Type: application/json" -d "{\"email\":\"tailleur@atelier.sn\",\"telephone\":\"772222222\",\"nom_complet\":\"Modou Tailleur\",\"mot_de_passe\":\"MotDePasse123\",\"role\":\"tailleur\"}"
```

| Rôle | Droits |
|---|---|
| **admin** | tout : comptes, catalogue, suppression de clients, annulation d'un paiement, statistiques |
| **accueil** | clients, commandes, paiements, livraisons ; peut annuler une commande |
| **tailleur** | prise et correction des mesures, avancement de la production ; **ne peut pas annuler** une commande |

Tout utilisateur connecté peut consulter clients, mesures, commandes, catalogue et livraisons.
Sans jeton valide : 401 ; rôle insuffisant : 403.

## Tests

Les tests utilisent la base `atelier_test` (créée par `docker/init-test-db.sql` au premier
démarrage du conteneur de base). Le schéma y est créé par Alembic, et les tables sont vidées après
chaque test. Les tests refusent de s'exécuter si `TEST_DATABASE_URL` est absente ou identique à
`DATABASE_URL`.

```powershell
docker compose up -d db
pytest -v
```

> Si le volume de la base existait avant l'ajout de `init-test-db.sql`, créez la base de test à la
> main : `docker compose exec db psql -U atelier -d atelier -c "CREATE DATABASE atelier_test;"`

### Règles de gestion et tests associés

| Règle | Fichier de test |
|---|---|
| RG1 téléphone unique et normalisé | `test_telephone.py`, `test_clients.py` |
| RG2 / RG3 mesures (au moins une, 0 < valeur ≤ 300, historique) | `test_mesures.py` |
| RG4 suppression d'un client / d'une mesure utilisés | `test_commandes.py` (`test_rg4_*`) |
| RG5 à RG9 numéro, prix, montants, date prévue, mesures automatiques | `test_commandes.py` |
| RG10 / RG12 lignes et commandes non modifiables | `test_commandes_modification.py` |
| RG11 commande en retard | `test_commandes.py` (`test_rg11_*`) |
| RG13 à RG15 workflow, annulation, historique | `test_statuts.py` |
| RG16 / RG17 paiements | `test_paiements.py` |
| RG18 à RG20 livraisons | `test_livraisons.py` |
| RG21 à RG23 mots de passe, jetons, échec de connexion | `test_auth.py` |
| RG24 protection du compte administrateur | `test_utilisateurs.py` |
| Droits de chaque route selon le rôle | `test_droits.py` |
| Statistiques | `test_statistiques.py` |
| Scénario de démonstration (annexe A) | `test_scenario_demo.py` |

## Liste des routes

Toutes les routes ont le préfixe `/api/v1`, sauf `/health`.

| N° | Méthode | Chemin | Rôle | Description |
|---|---|---|---|---|
| 1 | POST | `/auth/login` | Public | Connexion (formulaire OAuth2 : e-mail ou téléphone + mot de passe) |
| 2 | GET | `/auth/me` | Connecté | Profil de l'utilisateur connecté |
| 3 | POST | `/utilisateurs` | Admin | Créer un compte |
| 4 | GET | `/utilisateurs` | Admin | Liste des comptes triés par nom |
| 5 | GET | `/utilisateurs/{id}` | Admin | Détail d'un compte |
| 6 | PATCH | `/utilisateurs/{id}` | Admin | Modifier nom, rôle, actif, mot de passe |
| 7 | POST | `/clients` | Tous | Créer un client |
| 8 | GET | `/clients` | Tous | Liste paginée (`q`, `genre`, `limit`, `offset`) |
| 9 | GET | `/clients/{id}` | Tous | Fiche client |
| 10 | PATCH | `/clients/{id}` | Tous | Modification partielle |
| 11 | DELETE | `/clients/{id}` | Admin | Supprimer (409 s'il a des commandes) |
| 12 | GET | `/clients/{id}/commandes` | Tous | Commandes du client (paginées) |
| 13 | GET | `/clients/{id}/resume` | Tous | Résumé : commandes, chiffre d'affaires, solde dû |
| 14 | POST | `/catalogue` | Admin | Ajouter une prestation |
| 15 | GET | `/catalogue` | Tous | Liste (`actifs_seulement`) |
| 16 | GET | `/catalogue/{id}` | Tous | Détail |
| 17 | PATCH | `/catalogue/{id}` | Admin | Modifier prix, délai, nom, actif |
| 18 | POST | `/clients/{id}/mesures` | Tailleur | Nouvelle prise de mesures |
| 19 | GET | `/clients/{id}/mesures` | Tous | Historique des prises |
| 20 | GET | `/clients/{id}/mesures/derniere` | Tous | Dernière prise |
| 21 | GET | `/mesures/{id}` | Tous | Une prise |
| 22 | PATCH | `/mesures/{id}` | Tailleur | Corriger une prise |
| 23 | DELETE | `/mesures/{id}` | Tailleur | Supprimer (409 si utilisée) |
| 24 | POST | `/commandes` | Accueil | Créer une commande |
| 25 | GET | `/commandes` | Tous | Liste paginée et filtrée |
| 26 | GET | `/commandes/{id}` | Tous | Détail complet |
| 27 | PATCH | `/commandes/{id}` | Accueil | Modifier mesure, date prévue, remise, notes |
| 28 | POST | `/commandes/{id}/statut` | Tous | Changer le statut (workflow) |
| 29 | GET | `/commandes/{id}/historique` | Tous | Historique des statuts |
| 30 | POST | `/commandes/{id}/lignes` | Accueil | Ajouter une ligne |
| 31 | DELETE | `/commandes/{id}/lignes/{ligne_id}` | Accueil | Retirer une ligne |
| 32 | POST | `/commandes/{id}/paiements` | Accueil | Encaisser un paiement |
| 33 | GET | `/commandes/{id}/paiements` | Tous | Paiements de la commande |
| 34 | DELETE | `/paiements/{id}` | Admin | Annuler un paiement |
| 35 | PUT | `/commandes/{id}/livraison` | Accueil | Planifier / replanifier la livraison |
| 36 | GET | `/commandes/{id}/livraison` | Tous | Livraison de la commande |
| 37 | POST | `/commandes/{id}/livraison/confirmer` | Accueil | Confirmer la livraison |
| 38 | GET | `/livraisons` | Tous | Liste de tournée |
| 39 | GET | `/statistiques/tableau-de-bord` | Admin | Tableau de bord |
| 40 | GET | `/statistiques/chiffre-affaires` | Admin | CA et encaissements par jour ou par mois |
| 41 | GET | `/statistiques/types-vetement` | Admin | Ventes par type de vêtement |
| 42 | GET | `/statistiques/top-clients` | Admin | Meilleurs clients |
| 43 | GET | `/statistiques/impayes` | Admin | Commandes non soldées |
| 44 | GET | `/health` | Public | Santé de l'API et de la base |

### Conventions

- Codes : 200 lecture/modification, 201 création, 204 suppression, 401 non authentifié,
  403 rôle insuffisant, 404 introuvable, 409 conflit, 422 données invalides.
- Erreurs : `{"detail": "message en français"}`.
- Pagination : `{"items": [...], "total": n, "limit": n, "offset": n}` (`limit` 20 par défaut, 100 maximum).
- Montants en entiers FCFA ; mesures en centimètres.

## Migrations

```powershell
alembic revision --autogenerate -m "description"   # nouvelle migration (relire le fichier généré !)
alembic upgrade head                               # appliquer les migrations
```
