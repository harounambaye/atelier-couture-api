from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

MODES_PAIEMENT = Literal["especes", "wave", "orange_money", "virement", "cheque"]


class PaiementCreation(BaseModel):
    montant: int = Field(gt=0, description="Montant en FCFA")
    mode: MODES_PAIEMENT
    reference: str | None = Field(default=None, max_length=100)
    date_paiement: date | None = None  # aujourd'hui par défaut


class PaiementLecture(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    commande_id: int
    montant: int
    mode: str
    reference: str | None
    date_paiement: date
    enregistre_par_id: int
    created_at: datetime
