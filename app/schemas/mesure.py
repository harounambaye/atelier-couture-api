from datetime import date

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.mesure import CHAMPS_MESURES


class MesureValeurs(BaseModel):
    """Les 18 mesures facultatives, en cm : strictement positives et au plus 300."""

    taille_cm: float | None = Field(default=None, gt=0, le=300)
    tour_cou: float | None = Field(default=None, gt=0, le=300)
    carrure_dos: float | None = Field(default=None, gt=0, le=300)
    longueur_epaule: float | None = Field(default=None, gt=0, le=300)
    tour_poitrine: float | None = Field(default=None, gt=0, le=300)
    tour_taille: float | None = Field(default=None, gt=0, le=300)
    tour_bassin: float | None = Field(default=None, gt=0, le=300)
    longueur_manche: float | None = Field(default=None, gt=0, le=300)
    tour_bras: float | None = Field(default=None, gt=0, le=300)
    tour_poignet: float | None = Field(default=None, gt=0, le=300)
    longueur_dos: float | None = Field(default=None, gt=0, le=300)
    longueur_haut: float | None = Field(default=None, gt=0, le=300)
    longueur_pantalon: float | None = Field(default=None, gt=0, le=300)
    tour_cuisse: float | None = Field(default=None, gt=0, le=300)
    tour_genou: float | None = Field(default=None, gt=0, le=300)
    bas_pantalon: float | None = Field(default=None, gt=0, le=300)
    entrejambe: float | None = Field(default=None, gt=0, le=300)
    longueur_robe: float | None = Field(default=None, gt=0, le=300)


class MesureCreation(MesureValeurs):
    date_prise: date | None = None  # aujourd'hui par défaut
    notes: str | None = None

    @model_validator(mode="after")
    def au_moins_une_mesure(self):
        # RG2 : une prise contient au moins une mesure
        for champ in CHAMPS_MESURES:
            if getattr(self, champ) is not None:
                return self
        raise ValueError("Une prise de mesures doit contenir au moins une mesure")


class MesureModification(MesureValeurs):
    # Envoyer une mesure à null la retire de la prise
    date_prise: date | None = None
    notes: str | None = None


class MesureLecture(MesureValeurs):
    model_config = ConfigDict(from_attributes=True)

    id: int
    client_id: int
    date_prise: date
    prise_par_id: int
    notes: str | None
