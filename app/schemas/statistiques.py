from datetime import date

from pydantic import BaseModel


class TableauDeBord(BaseModel):
    # Mois courant
    chiffre_affaires_mois: int
    encaisse_mois: int
    nb_commandes_mois: int
    # Vue d'ensemble
    reste_a_encaisser: int
    commandes_par_statut: dict[str, int]
    nb_commandes_en_retard: int
    commandes_pretes_a_livrer: int
    livraisons_du_jour: int


class PeriodeChiffreAffaires(BaseModel):
    periode: str  # "2026-11-08" (jour) ou "2026-11" (mois)
    chiffre_affaires: int
    encaissements: int
    nb_commandes: int


class ChiffreAffaires(BaseModel):
    granularite: str
    date_debut: date
    date_fin: date
    periodes: list[PeriodeChiffreAffaires]


class StatistiqueTypeVetement(BaseModel):
    type_vetement_id: int
    nom: str
    quantite_vendue: int
    chiffre_affaires_avant_remise: int


class StatistiqueClient(BaseModel):
    client_id: int
    client_nom: str
    nb_commandes: int
    chiffre_affaires: int
    solde_du: int
