from pydantic import BaseModel, ConfigDict, Field, field_validator


class TypeVetementCreation(BaseModel):
    nom: str = Field(min_length=1, max_length=100)
    description: str | None = None
    prix_base: int = Field(ge=0, description="Prix en FCFA")
    delai_jours: int = Field(ge=0)

    @field_validator("nom")
    @classmethod
    def nom_non_vide(cls, valeur: str) -> str:
        valeur = valeur.strip()
        if valeur == "":
            raise ValueError("Le nom ne peut pas être vide")
        return valeur


class TypeVetementModification(BaseModel):
    nom: str | None = Field(default=None, max_length=100)
    description: str | None = None
    prix_base: int | None = Field(default=None, ge=0)
    delai_jours: int | None = Field(default=None, ge=0)
    actif: bool | None = None

    @field_validator("nom")
    @classmethod
    def nom_non_vidable(cls, valeur: str | None) -> str:
        if valeur is None or valeur.strip() == "":
            raise ValueError("Le nom ne peut pas être vidé")
        return valeur.strip()

    @field_validator("prix_base", "delai_jours", "actif")
    @classmethod
    def valeur_non_vidable(cls, valeur):
        if valeur is None:
            raise ValueError("Ce champ ne peut pas être vidé")
        return valeur


class TypeVetementLecture(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nom: str
    description: str | None
    prix_base: int
    delai_jours: int
    actif: bool
