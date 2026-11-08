from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.livraison import LivraisonLecture
from app.schemas.paiement import PaiementLecture

STATUTS_COMMANDE = Literal[
    "en_attente",
    "en_coupe",
    "en_couture",
    "essayage",
    "retouches",
    "terminee",
    "livree",
    "annulee",
]


# ---------- Création / modification ----------


class LigneCommandeCreation(BaseModel):
    type_vetement_id: int
    description: str | None = None
    quantite: int = Field(gt=0)
    # Si absent : prix_base du catalogue (RG6)
    prix_unitaire: int | None = Field(default=None, ge=0)


class CommandeCreation(BaseModel):
    client_id: int
    mesure_id: int | None = None
    lignes: list[LigneCommandeCreation] = Field(min_length=1)
    remise: int = Field(default=0, ge=0)
    date_livraison_prevue: date | None = None
    notes: str | None = None


class CommandeModification(BaseModel):
    mesure_id: int | None = None
    date_livraison_prevue: date | None = None
    remise: int | None = Field(default=None, ge=0)
    notes: str | None = None

    @field_validator("date_livraison_prevue", "remise")
    @classmethod
    def non_vidable(cls, valeur):
        if valeur is None:
            raise ValueError("Ce champ ne peut pas être vidé")
        return valeur


class ChangementStatut(BaseModel):
    statut: STATUTS_COMMANDE
    commentaire: str | None = None


# ---------- Lecture ----------


class LigneCommandeLecture(BaseModel):
    id: int
    type_vetement_id: int
    type_vetement_nom: str
    description: str | None
    quantite: int
    prix_unitaire: int
    sous_total: int


class HistoriqueStatutLecture(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ancien_statut: str | None
    nouveau_statut: str
    commentaire: str | None
    utilisateur_id: int
    date_changement: datetime


class CommandeResume(BaseModel):
    """Un élément de liste de commandes."""

    id: int
    numero: str
    client_id: int
    client_nom: str
    statut: str
    date_commande: date
    date_livraison_prevue: date
    date_livraison_reelle: date | None
    remise: int
    montant_total: int
    montant_paye: int
    solde: int
    en_retard: bool


class CommandeDetail(CommandeResume):
    mesure_id: int | None
    notes: str | None
    cree_par_id: int
    created_at: datetime
    updated_at: datetime
    lignes: list[LigneCommandeLecture]
    paiements: list[PaiementLecture]
    livraison: LivraisonLecture | None


class ResumeClient(BaseModel):
    nb_commandes: int
    chiffre_affaires: int
    total_paye: int
    solde_du: int
    derniere_commande: date | None
    a_des_mesures: bool
