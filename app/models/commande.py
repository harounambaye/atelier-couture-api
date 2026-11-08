from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

STATUTS = [
    "en_attente",
    "en_coupe",
    "en_couture",
    "essayage",
    "retouches",
    "terminee",
    "livree",
    "annulee",
]


class Commande(Base):
    __tablename__ = "commandes"

    id: Mapped[int] = mapped_column(primary_key=True)
    numero: Mapped[str] = mapped_column(String(30), unique=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"))
    mesure_id: Mapped[int | None] = mapped_column(ForeignKey("mesures.id"))
    statut: Mapped[str] = mapped_column(String(20), default="en_attente")
    date_commande: Mapped[date] = mapped_column(Date)
    date_livraison_prevue: Mapped[date] = mapped_column(Date)
    date_livraison_reelle: Mapped[date | None] = mapped_column(Date)
    remise: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    montant_total: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    montant_paye: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    notes: Mapped[str | None] = mapped_column(Text)
    cree_par_id: Mapped[int] = mapped_column(ForeignKey("utilisateurs.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    client = relationship("Client")
    lignes = relationship(
        "LigneCommande", cascade="all, delete-orphan", order_by="LigneCommande.id"
    )
    paiements = relationship(
        "Paiement", cascade="all, delete-orphan", order_by="Paiement.id"
    )
    historique = relationship(
        "HistoriqueStatut",
        cascade="all, delete-orphan",
        order_by="HistoriqueStatut.date_changement, HistoriqueStatut.id",
    )
    livraison = relationship("Livraison", cascade="all, delete-orphan", uselist=False)

    __table_args__ = (
        CheckConstraint(
            "statut IN ('en_attente', 'en_coupe', 'en_couture', 'essayage', "
            "'retouches', 'terminee', 'livree', 'annulee')",
            name="statut_valide",
        ),
        CheckConstraint("remise >= 0", name="remise_positive"),
        CheckConstraint("montant_total >= 0", name="montant_total_positif"),
        CheckConstraint("montant_paye >= 0", name="montant_paye_positif"),
    )


class LigneCommande(Base):
    __tablename__ = "lignes_commande"

    id: Mapped[int] = mapped_column(primary_key=True)
    commande_id: Mapped[int] = mapped_column(ForeignKey("commandes.id"))
    type_vetement_id: Mapped[int] = mapped_column(ForeignKey("types_vetement.id"))
    description: Mapped[str | None] = mapped_column(Text)
    quantite: Mapped[int] = mapped_column(Integer)
    prix_unitaire: Mapped[int] = mapped_column(Integer)  # FCFA

    type_vetement = relationship("TypeVetement")

    __table_args__ = (
        CheckConstraint("quantite > 0", name="quantite_positive"),
        CheckConstraint("prix_unitaire >= 0", name="prix_unitaire_positif"),
    )


class HistoriqueStatut(Base):
    __tablename__ = "historique_statuts"

    id: Mapped[int] = mapped_column(primary_key=True)
    commande_id: Mapped[int] = mapped_column(ForeignKey("commandes.id"))
    ancien_statut: Mapped[str | None] = mapped_column(String(20))  # vide à la création
    nouveau_statut: Mapped[str] = mapped_column(String(20))
    commentaire: Mapped[str | None] = mapped_column(Text)
    utilisateur_id: Mapped[int] = mapped_column(ForeignKey("utilisateurs.id"))
    date_changement: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    utilisateur = relationship("Utilisateur")
