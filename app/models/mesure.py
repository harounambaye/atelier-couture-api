from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

# Les 18 mesures facultatives, en centimètres
CHAMPS_MESURES = [
    "taille_cm",
    "tour_cou",
    "carrure_dos",
    "longueur_epaule",
    "tour_poitrine",
    "tour_taille",
    "tour_bassin",
    "longueur_manche",
    "tour_bras",
    "tour_poignet",
    "longueur_dos",
    "longueur_haut",
    "longueur_pantalon",
    "tour_cuisse",
    "tour_genou",
    "bas_pantalon",
    "entrejambe",
    "longueur_robe",
]


class Mesure(Base):
    __tablename__ = "mesures"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Supprimer un client supprime ses mesures (ON DELETE CASCADE)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"))
    date_prise: Mapped[date] = mapped_column(Date)
    prise_par_id: Mapped[int] = mapped_column(ForeignKey("utilisateurs.id"))
    notes: Mapped[str | None] = mapped_column(Text)
    taille_cm: Mapped[float | None] = mapped_column(Float)
    tour_cou: Mapped[float | None] = mapped_column(Float)
    carrure_dos: Mapped[float | None] = mapped_column(Float)
    longueur_epaule: Mapped[float | None] = mapped_column(Float)
    tour_poitrine: Mapped[float | None] = mapped_column(Float)
    tour_taille: Mapped[float | None] = mapped_column(Float)
    tour_bassin: Mapped[float | None] = mapped_column(Float)
    longueur_manche: Mapped[float | None] = mapped_column(Float)
    tour_bras: Mapped[float | None] = mapped_column(Float)
    tour_poignet: Mapped[float | None] = mapped_column(Float)
    longueur_dos: Mapped[float | None] = mapped_column(Float)
    longueur_haut: Mapped[float | None] = mapped_column(Float)
    longueur_pantalon: Mapped[float | None] = mapped_column(Float)
    tour_cuisse: Mapped[float | None] = mapped_column(Float)
    tour_genou: Mapped[float | None] = mapped_column(Float)
    bas_pantalon: Mapped[float | None] = mapped_column(Float)
    entrejambe: Mapped[float | None] = mapped_column(Float)
    longueur_robe: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
