#!/bin/sh
# Script de démarrage du conteneur de l'API
set -e

echo "Application des migrations Alembic..."
alembic upgrade head

echo "Seed : administrateur et catalogue de départ (idempotent)..."
python -m app.seed

echo "Démarrage de l'API..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
