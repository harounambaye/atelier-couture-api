from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.services.telephone import normaliser_telephone, telephone_est_valide


class UtilisateurCreation(BaseModel):
    email: EmailStr
    telephone: str
    nom_complet: str = Field(min_length=1, max_length=150)
    mot_de_passe: str = Field(min_length=8)
    role: Literal["admin", "tailleur", "accueil"]

    @field_validator("email")
    @classmethod
    def email_en_minuscules(cls, valeur: str) -> str:
        return valeur.lower()

    @field_validator("telephone")
    @classmethod
    def verifier_telephone(cls, valeur: str) -> str:
        telephone = normaliser_telephone(valeur)
        if not telephone_est_valide(telephone):
            raise ValueError("Numéro de téléphone invalide : 6 à 20 chiffres, « + » initial facultatif")
        return telephone


class UtilisateurModification(BaseModel):
    nom_complet: str | None = Field(default=None, min_length=1, max_length=150)
    role: Literal["admin", "tailleur", "accueil"] | None = None
    actif: bool | None = None
    mot_de_passe: str | None = Field(default=None, min_length=8)


class UtilisateurLecture(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    telephone: str
    nom_complet: str
    role: str
    actif: bool
    created_at: datetime
