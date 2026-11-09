FROM python:3.13-slim

# Pas de fichiers .pyc, et des logs affichés immédiatement
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /code

# On installe d'abord les dépendances (cette couche est mise en cache tant que requirements.txt ne change pas)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Puis le code de l'application et les migrations
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini .
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8000

# Au démarrage : migrations, seed, puis lancement de l'API
ENTRYPOINT ["/entrypoint.sh"]
