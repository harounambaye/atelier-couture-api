from fastapi import FastAPI
app = FastAPI(
    title="API Atelier de couture",
    description="Gestion des clients, mesures, commandes, paiements et livraison.",
    version="1.0.0",
)

@app.get("/health", tags=["Santé"])
def health():
    # Version provisoire
    return {"status":"OK", "message":"L'API est opérationnelle."}