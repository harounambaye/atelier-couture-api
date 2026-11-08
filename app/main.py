from fastapi import FastAPI

from app.routers import auth, catalogue, clients, health, mesures, utilisateurs

PREFIXE_API = "/api/v1"

app = FastAPI(
    title="API Atelier de couture",
    description="Gestion des clients, mesures, commandes, paiements et livraisons.",
    version="1.0.0",
)

app.include_router(health.router)
app.include_router(auth.router, prefix=PREFIXE_API)
app.include_router(utilisateurs.router, prefix=PREFIXE_API)
app.include_router(clients.router, prefix=PREFIXE_API)
app.include_router(catalogue.router, prefix=PREFIXE_API)
app.include_router(mesures.router, prefix=PREFIXE_API)
