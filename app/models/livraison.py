from datetime import date

from sqlalchemy import CheckConstraint, Date, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Livraison(Base):
    __tablename__ = "livraisons"

    id: Mapped[int] = mapped_column(primary_key=True)
    # unique : une seule livraison par commande
    commande_id: Mapped[int] = mapped_column(ForeignKey("commandes.id"), unique=True)
    mode: Mapped[str] = mapped_column(String(20))
    adresse: Mapped[str | None] = mapped_column(String(255))
    livreur: Mapped[str | None] = mapped_column(String(150))
    date_prevue: Mapped[date] = mapped_column(Date)
    date_effective: Mapped[date | None] = mapped_column(Date)
    statut: Mapped[str] = mapped_column(String(20), default="planifiee")
    notes: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint("mode IN ('retrait_atelier', 'domicile')", name="mode_valide"),
        CheckConstraint("statut IN ('planifiee', 'livree')", name="statut_valide"),
    )
