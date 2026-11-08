from fastapi import FastAPI

from app.routers import health

app = FastAPI(
    title="API Atelier de couture",
    description="Gestion des clients, mesures, commandes, paiements et livraisons.",
    version="1.0.0",
)

app.include_router(health.router)

