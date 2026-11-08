from datetime import datetime

from pydantic import BaseModel, ConfigDict


class UtilisateurLecture(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    telephone: str
    nom_complet: str
    role: str
    actif: bool
    created_at: datetime