from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.services.telephone import verifier_telephone


class ClientCreation(BaseModel):
    nom: str = Field(min_length=1, max_length=100)
    prenom: str = Field(min_length=1, max_length=100)
    telephone: str
    email: EmailStr | None = None
    adresse: str | None = Field(default=None, max_length=255)
    genre: Literal["homme", "femme", "enfant"]
    notes: str | None = None

    @field_validator("nom", "prenom")
    @classmethod
    def texte_non_vide(cls, valeur: str) -> str:
        valeur = valeur.strip()
        if valeur == "":
            raise ValueError("Ce champ ne peut pas être vide")
        return valeur

    @field_validator("telephone")
    @classmethod
    def verifier_telephone_client(cls, valeur: str) -> str:
        return verifier_telephone(valeur)


class ClientModification(BaseModel):
    # nom, prenom, telephone et genre peuvent être absents, mais pas vidés
    nom: str | None = Field(default=None, max_length=100)
    prenom: str | None = Field(default=None, max_length=100)
    telephone: str | None = None
    email: EmailStr | None = None
    adresse: str | None = Field(default=None, max_length=255)
    genre: Literal["homme", "femme", "enfant"] | None = None
    notes: str | None = None

    @field_validator("nom", "prenom")
    @classmethod
    def texte_non_vidable(cls, valeur: str | None) -> str:
        if valeur is None or valeur.strip() == "":
            raise ValueError("Ce champ ne peut pas être vidé")
        return valeur.strip()

    @field_validator("telephone")
    @classmethod
    def telephone_non_vidable(cls, valeur: str | None) -> str:
        if valeur is None:
            raise ValueError("Le téléphone ne peut pas être vidé")
        return verifier_telephone(valeur)

    @field_validator("genre")
    @classmethod
    def genre_non_vidable(cls, valeur: str | None) -> str:
        if valeur is None:
            raise ValueError("Le genre ne peut pas être vidé")
        return valeur


class ClientLecture(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nom: str
    prenom: str
    telephone: str
    email: str | None
    adresse: str | None
    genre: str
    notes: str | None
    created_at: datetime
    updated_at: datetime
